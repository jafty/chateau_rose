from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking, Provider, Service


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


    def test_provider_can_propose_update_from_detail(self):
        booking = self._create_booking()
        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])

        response = self.client.post(
            detail_url,
            {
                "action": "propose",
                "proposed_price_euros": "72,00",
                "proposed_date": "2026-02-01T10:00",
            },
            follow=True,
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(booking.status, "PENDING_CLIENT_VALIDATION")
        self.assertEqual(booking.proposed_price_cents, 7200)
        self.assertEqual(booking.proposed_date, "2026-02-01T10:00")

    def test_provider_can_propose_only_price(self):
        booking = self._create_booking()
        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])

        response = self.client.post(
            detail_url,
            {
                "action": "propose",
                "proposed_price_euros": "80",
                "proposed_date": "",
            },
            follow=True,
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(booking.status, "PENDING_CLIENT_VALIDATION")
        self.assertEqual(booking.proposed_price_cents, 8000)
        self.assertIsNone(booking.proposed_date)

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
