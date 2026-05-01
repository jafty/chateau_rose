from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking, Provider, Service


class _PaymentGatewayStub:
    def __init__(self):
        self.released = []

    def release_auth(self, auth_id: str):
        self.released.append(auth_id)


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
class BookingActionTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Diva")
        self.service = Service.objects.create(
            provider=self.provider,
            name="Tresses",
            slug="tresses",
            base_price_cents=5000,
            hair_length_adjustments={"long": 2000},
        )

    def test_client_action_expired_booking_redirects_to_confirmation_instead_of_500(self):
        from interface import views

        payment_stub = _PaymentGatewayStub()
        notifier_stub = _NotifierStub()

        original_gateway = views.payment_gateway
        original_notifier = views.notifier
        views.payment_gateway = payment_stub
        views.notifier = notifier_stub
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)
        self.addCleanup(setattr, views, "notifier", original_notifier)

        booking = Booking.objects.create(
            booking_id="BK-EXPIRED-1",
            provider=self.provider,
            service=self.service,
            client_name="Léa",
            client_email="lea@example.com",
            location="Paris",
            location_preference="salon",
            client_address="",
            desired_date=(timezone.now() + timedelta(days=2)).isoformat(),
            hair_length="long",
            general_adjustments=[],
            meche=False,
            current_hair_picture="current.jpg",
            inspiration_pictures=[],
            free_text="",
            estimated_price_cents=9000,
            payment_auth_id="pi_auth_expired",
            status="SUBMITTED",
            created_at=timezone.now() - timedelta(hours=73),
        )

        response = self.client.post(
            reverse("interface:client_action", args=[booking.booking_id]),
            data={"decision": "refuse"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("interface:client_confirmation", args=[booking.booking_id]) + "?status=expired",
        )

        booking.refresh_from_db()
        self.assertEqual(booking.status, "CANCELLED")
        self.assertEqual(payment_stub.released, ["pi_auth_expired"])
        self.assertEqual(len(notifier_stub.messages), 2)

        confirmation = self.client.get(reverse("interface:client_confirmation", args=[booking.booking_id]), data={"status": "expired"})
        self.assertContains(confirmation, "Cette demande a expiré après 72h sans confirmation")

    def test_admin_cancel_can_cancel_expired_uncaptured_booking(self):
        from interface import views

        payment_stub = _PaymentGatewayStub()
        notifier_stub = _NotifierStub()

        original_gateway = views.payment_gateway
        original_notifier = views.notifier
        views.payment_gateway = payment_stub
        views.notifier = notifier_stub
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)
        self.addCleanup(setattr, views, "notifier", original_notifier)

        user_model = get_user_model()
        admin = user_model.objects.create_user(
            username="admin-cancel",
            email="admin@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.client.force_login(admin)

        booking = Booking.objects.create(
            booking_id="BK-ADMIN-EXPIRED-1",
            provider=self.provider,
            service=self.service,
            client_name="Léa",
            client_email="lea@example.com",
            location="Paris",
            location_preference="salon",
            client_address="",
            desired_date=(timezone.now() + timedelta(days=2)).isoformat(),
            hair_length="long",
            general_adjustments=[],
            meche=False,
            current_hair_picture="current.jpg",
            inspiration_pictures=[],
            free_text="",
            estimated_price_cents=9000,
            payment_auth_id="pi_auth_admin_expired",
            status="SUBMITTED",
            created_at=timezone.now() - timedelta(hours=73),
        )

        response = self.client.post(reverse("interface:cancel_booking_admin", args=[booking.booking_id]))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("providers:booking_detail", args=[booking.booking_id]))

        booking.refresh_from_db()
        self.assertEqual(booking.status, "CANCELLED")
        self.assertEqual(payment_stub.released, ["pi_auth_admin_expired"])
        self.assertEqual(len(notifier_stub.messages), 2)

    def test_client_confirmation_uses_locked_reservation_fee_when_present(self):
        booking = Booking.objects.create(
            booking_id="BK-LOCKED-FEE-1",
            provider=self.provider,
            service=self.service,
            client_name="Léa",
            client_email="lea@example.com",
            location="Paris",
            location_preference="salon",
            client_address="",
            desired_date=(timezone.now() + timedelta(days=2)).isoformat(),
            hair_length="long",
            general_adjustments=[],
            meche=False,
            current_hair_picture="current.jpg",
            inspiration_pictures=[],
            free_text="",
            estimated_price_cents=5175,
            payment_auth_id="pi_auth_locked",
            status="SUBMITTED",
            locked_reservation_fee_cents=2025,
            created_at=timezone.now(),
        )

        response = self.client.get(reverse("interface:client_confirmation", args=[booking.booking_id]))

        self.assertContains(response, "Empreinte bancaire validée")
        self.assertContains(response, "20.75 €")
        self.assertContains(response, "Acompte prestataire : 14 €")
        self.assertContains(response, "Montant à régler le jour J :")

    def test_client_confirmation_applies_ceil_deposit_and_floor_remaining(self):
        booking = Booking.objects.create(
            booking_id="BK-ROUNDING-1",
            provider=self.provider,
            service=self.service,
            client_name="Nina",
            client_email="nina@example.com",
            location="Paris",
            location_preference="salon",
            client_address="",
            desired_date=(timezone.now() + timedelta(days=2)).isoformat(),
            hair_length="long",
            general_adjustments=[],
            meche=False,
            current_hair_picture="current.jpg",
            inspiration_pictures=[],
            free_text="",
            estimated_price_cents=8625,
            payment_auth_id="pi_auth_rounding",
            status="SUBMITTED",
            created_at=timezone.now(),
        )

        response = self.client.get(reverse("interface:client_confirmation", args=[booking.booking_id]))

        self.assertContains(response, "Total estimé :")
        self.assertContains(response, "86.25 €")
        self.assertContains(response, "Empreinte bancaire validée")
        self.assertContains(response, "34.25 €")
        self.assertContains(response, "Frais Château Rose : 11.25 €")
        self.assertContains(response, "Acompte prestataire : 23 €")
        self.assertContains(response, "Montant à régler le jour J")
        self.assertContains(response, "52 €")
