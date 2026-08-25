from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking, BookingOffer, BookingOpportunity, Provider, Service
from chateaurose.domain.exceptions import InvalidState
from chateaurose.infrastructure.bounty_service import (
    accept_unchanged,
    eligible_services,
    open_for_booking,
)
from interface.models import MarketingService, MarketingSubService


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
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
        provider_email = notify.call_args.args[2]
        self.assertTrue(provider_email.startswith("Bonjour Candidate,"))
        self.assertIn("Prestation : Knotless S", provider_email)
        self.assertIn("L'équipe Château Rose", provider_email)

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

    @patch(
        "chateaurose.infrastructure.bounty_service.notifier.notify", return_value=True
    )
    def test_provider_offer_prefills_the_generic_estimated_price(self, notify):
        opportunity = open_for_booking(
            self.booking().booking_id, reason=BookingOpportunity.REASON_GENERIC
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("providers:bounty_offer", args=[opportunity.id])
        )

        self.assertContains(response, 'value="100.00"')
        self.assertContains(
            response,
            "Estimation calculée lors de la demande : 100.00 €",
        )

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

    @patch("chateaurose.infrastructure.bounty_service.payments.capture_auth")
    @patch(
        "chateaurose.infrastructure.bounty_service.notifier.notify", return_value=True
    )
    def test_direct_acceptance_captures_and_preserves_canonical_terms(
        self, notify, capture
    ):
        booking = self.booking(payment_auth_id="auth_direct")
        opportunity = open_for_booking(
            booking.booking_id, reason=BookingOpportunity.REASON_GENERIC
        )
        original_date = booking.desired_date

        confirmed, offer = accept_unchanged(
            opportunity_id=opportunity.id,
            provider=self.candidate,
            service_id=self.candidate_service.id,
        )

        capture.assert_called_once_with("auth_direct")
        self.assertEqual(confirmed.status, Booking.STATUS_CONFIRMED)
        self.assertEqual(confirmed.desired_date, original_date)
        self.assertEqual(confirmed.provider_price_estimate_cents, 10000)
        self.assertEqual(confirmed.estimated_price_cents, 11500)
        self.assertEqual(confirmed.chateau_rose_fee_cents, 1500)
        self.assertEqual(confirmed.payment_status, Booking.PAYMENT_STATUS_CAPTURED)
        self.assertEqual(offer.status, BookingOffer.STATUS_DIRECTLY_ACCEPTED)
        self.assertEqual(notify.call_count, 3)  # invitation, then both confirmations
        self.assertIn("Ta demande est confirmée", notify.call_args_list[-2].args[1])

        with self.assertRaises(InvalidState):
            accept_unchanged(
                opportunity_id=opportunity.id,
                provider=self.candidate,
                service_id=self.candidate_service.id,
            )
        self.assertEqual(
            BookingOffer.objects.filter(opportunity=opportunity).count(), 1
        )

    @patch(
        "chateaurose.infrastructure.bounty_service.payments.capture_auth",
        side_effect=RuntimeError("gateway unavailable"),
    )
    @patch(
        "chateaurose.infrastructure.bounty_service.notifier.notify", return_value=True
    )
    def test_gateway_failure_rolls_back_direct_acceptance(self, notify, capture):
        booking = self.booking(booking_id="BK-GATEWAY", payment_auth_id="auth_fail")
        opportunity = open_for_booking(
            booking.booking_id, reason=BookingOpportunity.REASON_GENERIC
        )

        with self.assertRaisesRegex(RuntimeError, "gateway unavailable"):
            accept_unchanged(
                opportunity_id=opportunity.id,
                provider=self.candidate,
                service_id=self.candidate_service.id,
            )

        booking.refresh_from_db()
        opportunity.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_BOUNTY_OPEN)
        self.assertEqual(booking.payment_status, Booking.PAYMENT_STATUS_AUTHORIZED)
        self.assertEqual(opportunity.status, BookingOpportunity.STATUS_OPEN)
        self.assertFalse(BookingOffer.objects.filter(opportunity=opportunity).exists())
        self.assertEqual(notify.call_count, 1)  # only the original invitation

    @patch(
        "chateaurose.infrastructure.bounty_service.notifier.notify", return_value=True
    )
    def test_changed_offer_still_requires_client_validation(self, notify):
        opportunity = open_for_booking(
            self.booking(booking_id="BK-CHANGED").booking_id,
            reason=BookingOpportunity.REASON_GENERIC,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("providers:bounty_offer", args=[opportunity.id]),
            {
                "action": "submit_offer",
                "service": self.candidate_service.id,
                "proposed_date": (timezone.now() + timedelta(days=5)).isoformat(),
                "proposed_price_euros": "120.00",
            },
        )
        self.assertEqual(response.status_code, 200)
        opportunity.booking.refresh_from_db()
        self.assertEqual(
            opportunity.booking.status, Booking.STATUS_BOUNTY_CLIENT_VALIDATION
        )
        self.assertEqual(opportunity.offer.status, BookingOffer.STATUS_PENDING_CLIENT)
