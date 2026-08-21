from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.test import TestCase
from django.utils import timezone

from booking.models import Booking, BookingOpportunity, Provider, Service
from chateaurose.infrastructure.bounty_service import (
    eligible_services,
    open_for_booking,
)
from interface.models import MarketingService, MarketingSubService


class BountyServiceTests(TestCase):
    def setUp(self):
        self.marketing_service = MarketingService.objects.create(
            name="Tresses", slug="tresses"
        )
        self.sub_service = MarketingSubService.objects.create(
            service=self.marketing_service, name="Knotless S", slug="knotless-s"
        )
        self.user = get_user_model().objects.create_user(
            username="candidate", password="secret"
        )
        self.candidate = Provider.objects.create(
            name="Candidate",
            user=self.user,
            contact_email="candidate@example.com",
            is_visible_on_website=True,
        )
        self.candidate_service = Service.objects.create(
            provider=self.candidate,
            name="Knotless",
            slug="knotless",
            base_price_cents=10000,
        )
        self.candidate_service.marketing_sub_services.add(self.sub_service)

    def booking(self, **changes):
        values = {
            "booking_id": "BK-BOUNTY",
            "booking_kind": Booking.KIND_GENERIC,
            "requested_marketing_service": self.marketing_service,
            "requested_marketing_sub_service": self.sub_service,
            "requested_service_label_snapshot": "Knotless S",
            "client_name": "Alice",
            "client_email": "alice@example.com",
            "location": "Toulouse",
            "desired_date": (timezone.now() + timedelta(days=4)).isoformat(),
            "hair_length": "standard",
            "meche": False,
            "estimated_price_cents": 11500,
            "provider_price_estimate_cents": 10000,
            "chateau_rose_fee_cents": 1500,
            "amount_due_now_cents": 1500,
            "payment_status": Booking.PAYMENT_STATUS_AUTHORIZED,
            "status": Booking.STATUS_WAITING_PROVIDER_ASSIGNMENT,
            "created_at": timezone.now(),
            "updated_at": timezone.now(),
            "state_entered_at": timezone.now(),
            "process_expires_at": timezone.now() + timedelta(days=6),
        }
        values.update(changes)
        return Booking.objects.create(**values)

    @patch(
        "chateaurose.infrastructure.bounty_service.notifier.notify", return_value=True
    )
    def test_generic_request_matches_exact_sub_service(self, notify):
        opportunity = open_for_booking(
            self.booking().booking_id, reason=BookingOpportunity.REASON_GENERIC
        )
        self.assertEqual(list(eligible_services(opportunity)), [self.candidate_service])
        self.assertEqual(opportunity.booking.status, Booking.STATUS_BOUNTY_OPEN)
        self.assertEqual(notify.call_count, 1)

    @patch(
        "chateaurose.infrastructure.bounty_service.notifier.notify", return_value=True
    )
    def test_booking_lock_does_not_join_nullable_relations(self, notify):
        booking = self.booking(booking_id="BK-LOCK-WITHOUT-JOIN")

        with CaptureQueriesContext(connection) as queries:
            open_for_booking(
                booking.booking_id, reason=BookingOpportunity.REASON_GENERIC
            )

        lock_query = next(
            query["sql"]
            for query in queries.captured_queries
            if 'FROM "booking_booking"' in query["sql"]
            and '"booking_booking"."booking_id"' in query["sql"]
        )
        self.assertNotIn(" JOIN ", lock_query.upper())

    @patch(
        "chateaurose.infrastructure.bounty_service.notifier.notify", return_value=True
    )
    def test_scheduled_command_opens_generic_opportunity(self, notify):
        booking = self.booking(booking_id="BK-SCHEDULED-GENERIC")

        call_command("process_bounties")

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_BOUNTY_OPEN)
        self.assertTrue(
            BookingOpportunity.objects.filter(
                booking=booking,
                reason=BookingOpportunity.REASON_GENERIC,
                status=BookingOpportunity.STATUS_OPEN,
            ).exists()
        )
        notify.assert_called_once()

    @patch("chateaurose.infrastructure.bounty_service.payments.release_auth")
    @patch(
        "chateaurose.infrastructure.bounty_service.notifier.notify", return_value=True
    )
    def test_malformed_provider_service_is_not_broadcast_broadly(self, notify, release):
        original = Provider.objects.create(
            name="Originale", contact_email="original@example.com"
        )
        malformed = Service.objects.create(
            provider=original,
            name="Ancien service",
            slug="ancien",
            base_price_cents=9000,
        )
        booking = self.booking(
            booking_id="BK-MALFORMED",
            booking_kind=Booking.KIND_PROVIDER_SELECTED,
            provider=original,
            service=malformed,
            requested_marketing_sub_service=None,
            status=Booking.STATUS_AWAITING_ALTERNATIVE_PROVIDER,
            payment_auth_id="pi_test",
        )
        result = open_for_booking(
            booking.booking_id, reason=BookingOpportunity.REASON_PROVIDER_REJECTED
        )
        booking.refresh_from_db()
        self.assertIsNone(result)
        self.assertEqual(booking.status, Booking.STATUS_CANCELLED)
        release.assert_called_once_with("pi_test")
        self.assertEqual(notify.call_count, 2)
