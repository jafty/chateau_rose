from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking, Provider, ProviderBlockedSlot, Service


class _PaymentGatewayStub:
    def __init__(self):
        self.released = []

    def release_auth(self, auth_id: str):
        self.released.append(auth_id)

    def capture_auth(self, auth_id: str):
        return None


class _NotifierStub:
    def __init__(self):
        self.messages = []

    def notify(self, recipient, subject, body, reply_to=None):
        self.messages.append(
            {
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "reply_to": reply_to,
            }
        )


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ProviderDashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="provider",
            password="safepass123",
            email="provider@example.com",
        )
        self.provider = Provider.objects.create(
            name="Coiffeuse Pro",
            description="",
            contact_phone="+33102030405",
            contact_email="provider@example.com",
            user=self.user,
        )
        self.service = Service.objects.create(
            provider=self.provider,
            name="Tresses",
            slug="tresses",
            base_price_cents=5000,
            hair_length_adjustments={"long": 1500},
        )
        self.client = Client()
        self.client.login(username="provider", password="safepass123")

    def _create_booking(self, status="SUBMITTED"):
        return Booking.objects.create(
            booking_id="BK-1234ABCD",
            provider=self.provider,
            service=self.service,
            client_name="Sarah",
            client_email="sarah@example.com",
            location="Paris",
            location_preference="domicile",
            client_address="5 place du Capitole, 31000 Toulouse",
            desired_date="2026-01-10T17:00:00Z",
            hair_length="long",
            meche=True,
            current_hair_picture="/media/hair.jpg",
            inspiration_pictures=[],
            free_text="",
            estimated_price_cents=6500,
            payment_auth_id="auth_1",
            status=status,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

    def test_dashboard_lists_clickable_bookings(self):
        booking = self._create_booking()

        response = self.client.get(reverse("providers:providers_index"))

        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])
        self.assertContains(response, detail_url)
        self.assertContains(response, booking.booking_id)

    def test_dashboard_auto_expires_stale_open_booking(self):
        from providers import views

        payment_stub = _PaymentGatewayStub()
        notifier_stub = _NotifierStub()

        original_gateway = views.payment_gateway
        original_notifier = views.notifier
        views.payment_gateway = payment_stub
        views.notifier = notifier_stub
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)
        self.addCleanup(setattr, views, "notifier", original_notifier)

        booking = self._create_booking(status="SUBMITTED")
        booking.created_at = timezone.now() - timedelta(hours=73)
        booking.save(update_fields=["created_at"])

        response = self.client.get(reverse("providers:providers_index"))

        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.status, "CANCELLED")
        self.assertEqual(payment_stub.released, ["auth_1"])
        self.assertEqual(len(notifier_stub.messages), 3)


    def test_provider_reject_transfers_booking_to_alternative_search(self):
        from providers import views

        payment_stub = _PaymentGatewayStub()
        notifier_stub = _NotifierStub()

        original_gateway = views.payment_gateway
        original_notifier = views.notifier
        views.payment_gateway = payment_stub
        views.notifier = notifier_stub
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)
        self.addCleanup(setattr, views, "notifier", original_notifier)

        booking = self._create_booking(status="SUBMITTED")
        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])

        response = self.client.post(detail_url, {"action": "reject"}, follow=True)

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(booking.status, "AWAITING_ALTERNATIVE_PROVIDER")
        self.assertIsNotNone(booking.alternative_requested_at)
        self.assertEqual(payment_stub.released, [])
        self.assertEqual(notifier_stub.messages[-1]["subject"], f"Alternative à trouver · {booking.booking_id}")

    def test_provider_can_propose_update_from_detail(self):
        booking = self._create_booking()
        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])

        response = self.client.post(
            detail_url,
            {
                "action": "propose",
                "proposed_price_euros": "50,00",
                "proposed_date": "2026-02-01T10:00",
            },
            follow=True,
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(booking.status, "PENDING_CLIENT_VALIDATION")
        self.assertEqual(booking.proposed_price_cents, 5000)
        self.assertEqual(booking.proposed_date, "2026-02-01T10:00")

    def test_provider_can_propose_only_price(self):
        booking = self._create_booking()
        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])

        response = self.client.post(
            detail_url,
            {
                "action": "propose",
                "proposed_price_euros": "58",
                "proposed_date": "",
            },
            follow=True,
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(booking.status, "PENDING_CLIENT_VALIDATION")
        self.assertEqual(booking.proposed_price_cents, 5800)
        self.assertIsNone(booking.proposed_date)

    def test_booking_detail_displays_optional_counter_proposal_message_field(self):
        booking = self._create_booking()
        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "name=\"counter_proposal_message\"")
        self.assertContains(response, "Empreinte déjà réservée")
        self.assertContains(response, "dont acompte prestataire")

    def test_provider_can_propose_only_date(self):
        booking = self._create_booking()
        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])

        response = self.client.post(
            detail_url,
            {
                "action": "propose",
                "proposed_price_euros": "",
                "proposed_date": "2026-02-05T11:30",
            },
            follow=True,
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(booking.status, "PENDING_CLIENT_VALIDATION")
        self.assertIsNone(booking.proposed_price_cents)
        self.assertEqual(booking.proposed_date, "2026-02-05T11:30")

    def test_booking_detail_uses_provider_deposit_percentage_for_payment_summary(self):
        self.provider.deposit_percentage = 10
        self.provider.save(update_fields=["deposit_percentage"])
        booking = self._create_booking()

        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])
        response = self.client.get(detail_url)

        self.assertContains(response, "Empreinte bancaire validée")
        self.assertContains(response, "14,48 €")
        self.assertContains(response, "Frais Château Rose : 8,48 €")
        self.assertContains(response, "Acompte prestataire : 6,00 €")
        self.assertContains(response, "50,00 €")

    def test_booking_detail_shows_photos_and_prices_in_euros(self):
        booking = self._create_booking()
        booking.inspiration_pictures = ["/media/inspo1.jpg", "/media/inspo2.jpg"]
        booking.save()

        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])
        response = self.client.get(detail_url)

        self.assertContains(response, "65,00 €")
        self.assertNotContains(response, "cts")
        self.assertContains(response, "src=\"/media/hair.jpg\"")
        self.assertContains(response, "src=\"/media/inspo1.jpg\"")
        self.assertContains(response, "src=\"/media/inspo2.jpg\"")

    def test_relative_photo_paths_are_resolved_with_media_url(self):
        booking = self._create_booking()
        booking.current_hair_picture = "bookings/current/test.jpg"
        booking.inspiration_pictures = ["bookings/inspiration/1.jpg", "/already/root.jpg"]
        booking.save()

        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])
        response = self.client.get(detail_url)

        self.assertContains(response, "src=\"/media/bookings/current/test.jpg\"")
        self.assertContains(response, "src=\"/media/bookings/inspiration/1.jpg\"")
        self.assertContains(response, "src=\"/already/root.jpg\"")

    def test_provider_can_confirm_booking_from_detail(self):
        booking = self._create_booking()
        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])

        response = self.client.post(detail_url, {"action": "confirm"}, follow=True)

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(booking.status, "CONFIRMED")

    def test_booking_detail_shows_confirmed_price(self):
        booking = self._create_booking(status="CONFIRMED")
        booking.estimated_price_cents = 5000
        booking.proposed_price_cents = 6000
        booking.save()

        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])
        response = self.client.get(detail_url)

        self.assertContains(response, "Tarif")
        self.assertContains(response, "60,00 €")
        self.assertNotContains(response, "50,00 €")

    def test_logout_via_post_logs_out_and_redirects(self):
        response = self.client.post(reverse("providers:logout"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        # Final redirect should land on the public home page
        self.assertTrue(any(url.endswith(reverse("interface:home")) for url, _ in response.redirect_chain))


class ProviderSignupTests(TestCase):
    def test_provider_can_register_and_login(self):
        client = Client()
        response = client.post(
            reverse("providers:signup"),
            {
                "username": "newprovider",
                "password1": "SafePassw0rd!",
                "password2": "SafePassw0rd!",
                "email": "new@pro.fr",
                "name": "Nouvelle Pro",
                "contact_email": "new@pro.fr",
                "contact_phone": "+33102030405",
                "location_mode": Provider.LOCATION_MODE_HYBRID,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        created_user = get_user_model().objects.get(username="newprovider")
        provider = Provider.objects.get(user=created_user)

        self.assertEqual(provider.name, "Nouvelle Pro")
        self.assertEqual(provider.contact_email, "new@pro.fr")
        self.assertEqual(provider.location_mode, Provider.LOCATION_MODE_HYBRID)
        self.assertTrue(response.wsgi_request.user.is_authenticated)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ProviderAccountTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="provider-account",
            password="safepass123",
        )
        self.provider = Provider.objects.create(
            name="Compte Pro",
            user=self.user,
        )
        self.service = Service.objects.create(
            provider=self.provider,
            name="Nattes",
            slug="nattes",
            base_price_cents=5500,
            hair_length_adjustments={"long": 1000},
            general_adjustments={"motif": 500},
        )
        self.client = Client()
        self.client.login(username="provider-account", password="safepass123")

    def test_provider_can_update_service_prices_and_adjustments_in_euros(self):
        response = self.client.post(
            reverse("providers:account"),
            {
                "action": "save_service",
                "service_id": self.service.id,
                "base_price_euros": "79,50",
                "meche_bonus_euros": "5",
                "at_home_bonus_euros": "12,5",
                "hair_label[]": ["long", "extra long"],
                "hair_price[]": ["10", "20,5"],
                "general_label[]": ["motif", "perles"],
                "general_price[]": ["3", "8,5"],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.service.refresh_from_db()
        self.assertEqual(self.service.base_price_cents, 7950)
        self.assertEqual(self.service.meche_bonus_cents, 500)
        self.assertEqual(self.service.at_home_bonus_cents, 1250)
        self.assertEqual(self.service.hair_length_adjustments, {"long": 1000, "extra long": 2050})
        self.assertEqual(self.service.general_adjustments, {"motif": 300, "perles": 850})

    def test_provider_account_page_displays_current_service_image_preview(self):
        self.service.image_url = "https://cdn.example.com/services/nattes.jpg"
        self.service.save(update_fields=["image_url"])

        response = self.client.get(reverse("providers:account"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.service.image_url)

    def test_provider_can_add_punctual_blocked_slot_with_default_message(self):
        response = self.client.post(
            reverse("providers:account"),
            {
                "action": "add_blocked_slot",
                "starts_at": "2026-06-10T10:00",
                "ends_at": "2026-06-10T12:00",
                "reason": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        slot = ProviderBlockedSlot.objects.get(provider=self.provider)
        self.assertFalse(slot.is_recurring)
        self.assertEqual(slot.reason, "Ce créneau n'est plus disponible")


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ProviderAdminModeTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_user(
            username="admin",
            password="safepass123",
            email="admin@example.com",
            is_staff=True,
        )
        self.provider_user = get_user_model().objects.create_user(
            username="provider2",
            password="safepass123",
            email="provider2@example.com",
        )
        self.provider = Provider.objects.create(
            name="Coiffeuse 2",
            contact_email="provider2@example.com",
            user=self.provider_user,
        )
        self.service = Service.objects.create(
            provider=self.provider,
            name="Vanilles",
            slug="vanilles",
            base_price_cents=7000,
        )
        self.booking = Booking.objects.create(
            booking_id="BK-ADM1N01",
            provider=self.provider,
            service=self.service,
            client_name="Lina",
            client_email="lina@example.com",
            location="Paris",
            location_preference="domicile",
            client_address="10 rue de Paris",
            desired_date="2026-01-10T17:00:00Z",
            hair_length="long",
            meche=True,
            current_hair_picture="/media/hair.jpg",
            inspiration_pictures=[],
            free_text="",
            estimated_price_cents=7000,
            payment_auth_id="auth_admin_1",
            status="SUBMITTED",
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        self.client = Client()
        self.client.login(username="admin", password="safepass123")

    def test_staff_without_provider_can_access_centralized_dashboard(self):
        response = self.client.get(reverse("providers:providers_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gestion centralisée des demandes")
        self.assertContains(response, self.provider.name)
        self.assertContains(response, self.booking.booking_id)


    def test_staff_can_cancel_pending_client_validation_booking(self):
        from interface import views

        class _GatewayStub:
            def release_auth(self, _auth_id):
                return None

            def capture_auth(self, _auth_id):
                return None

        original_gateway = views.payment_gateway
        views.payment_gateway = _GatewayStub()
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)

        self.booking.status = "PENDING_CLIENT_VALIDATION"
        self.booking.save(update_fields=["status"])

        response = self.client.post(
            reverse("interface:cancel_booking_admin", args=[self.booking.booking_id]),
            follow=True,
        )

        self.booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.booking.status, "CANCELLED")

    def test_staff_without_provider_can_manage_booking_detail(self):
        detail_url = reverse("providers:booking_detail", args=[self.booking.booking_id])
        response = self.client.post(
            detail_url,
            {
                "action": "propose",
                "proposed_price_euros": "75",
                "proposed_date": "2026-03-01T10:30",
            },
            follow=True,
        )

        self.booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.booking.status, "PENDING_CLIENT_VALIDATION")
        self.assertEqual(self.booking.proposed_price_cents, 7500)
