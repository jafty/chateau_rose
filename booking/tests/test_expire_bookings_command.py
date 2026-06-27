from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
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


class ExpireBookingsCommandTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Diva")
        self.service = Service.objects.create(
            provider=self.provider,
            name="Tresses",
            slug="tresses",
            base_price_cents=5000,
            hair_length_adjustments={"long": 2000},
        )

    def _create_booking(self, booking_id: str, *, status: str, created_at):
        booking = Booking.objects.create(
            booking_id=booking_id,
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
            payment_auth_id=f"pi_auth_{booking_id}",
            status=status,
            created_at=created_at,
        )
        Booking.objects.filter(pk=booking.pk).update(created_at=created_at)
        booking.refresh_from_db()
        return booking

    def test_command_moves_stale_submitted_booking_to_alternative_search(self):
        old_booking = self._create_booking(
            "BK-OLD-1",
            status="SUBMITTED",
            created_at=timezone.now() - timedelta(hours=73),
        )
        fresh_booking = self._create_booking(
            "BK-FRESH-1",
            status="SUBMITTED",
            created_at=timezone.now() - timedelta(hours=20),
        )

        payment_stub = _PaymentGatewayStub()
        notifier_stub = _NotifierStub()

        with (
            patch("booking.management.commands.expire_bookings.StripePaymentGateway", return_value=payment_stub),
            patch("booking.management.commands.expire_bookings.EmailNotifier", return_value=notifier_stub),
        ):
            call_command("expire_bookings")

        old_booking.refresh_from_db()
        fresh_booking.refresh_from_db()

        self.assertEqual(old_booking.status, Booking.STATUS_AWAITING_ALTERNATIVE_PROVIDER)
        self.assertEqual(fresh_booking.status, "SUBMITTED")
        self.assertEqual(payment_stub.released, [])
        self.assertEqual(len(notifier_stub.messages), 2)
