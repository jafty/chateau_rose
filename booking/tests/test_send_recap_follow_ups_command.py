from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from booking.models import Booking, Provider, Service
from interface.models import MarketingService, MarketingSubService, ProviderBookingDraft


@override_settings(SITE_URL="https://example.test")
class SendRecapFollowUpsCommandTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Diva")
        self.service = Service.objects.create(
            provider=self.provider, name="Braids", slug="braids", base_price_cents=10000
        )

    def _draft(self, **overrides):
        values = {
            "provider": self.provider,
            "client_email": "client@example.com",
            "client_name": "Sarah",
            "payload": {
                "service_id": str(self.service.id),
                "desired_date": "2026-09-10T10:00",
            },
        }
        values.update(overrides)
        draft = ProviderBookingDraft.objects.create(**values)
        ProviderBookingDraft.objects.filter(pk=draft.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        draft.refresh_from_db()
        return draft

    @patch(
        "booking.management.commands.send_recap_follow_ups.EmailNotifier.notify",
        return_value=True,
    )
    def test_sends_one_follow_up_after_24_hours(self, notify):
        draft = self._draft()

        call_command("send_recap_follow_ups")
        call_command("send_recap_follow_ups")

        draft.refresh_from_db()
        self.assertIsNotNone(draft.follow_up_sent_at)
        notify.assert_called_once()
        self.assertEqual(
            notify.call_args.args[1], "Souhaites-tu toujours prendre rendez-vous ?"
        )
        self.assertIn(str(draft.token), notify.call_args.args[2])

    @patch(
        "booking.management.commands.send_recap_follow_ups.EmailNotifier.notify",
        return_value=True,
    )
    def test_matching_booking_suppresses_all_duplicate_recaps(self, notify):
        first = self._draft()
        second = self._draft()
        Booking.objects.create(
            booking_id="validated",
            booking_kind=Booking.KIND_PROVIDER_SELECTED,
            provider=self.provider,
            service=self.service,
            client_name="Sarah",
            client_email="CLIENT@example.com",
            location="Paris",
            desired_date="2026-09-10T10:00",
            hair_length="long",
            meche=False,
            estimated_price_cents=10000,
            status=Booking.STATUS_SUBMITTED,
            created_at=max(first.created_at, second.created_at) + timedelta(minutes=1),
        )

        call_command("send_recap_follow_ups")

        notify.assert_not_called()

    @patch(
        "booking.management.commands.send_recap_follow_ups.EmailNotifier.notify",
        return_value=True,
    )
    def test_older_booking_does_not_suppress_returning_client(self, notify):
        Booking.objects.create(
            booking_id="old",
            booking_kind=Booking.KIND_PROVIDER_SELECTED,
            provider=self.provider,
            service=self.service,
            client_name="Sarah",
            client_email="client@example.com",
            location="Paris",
            desired_date="2026-09-10T10:00",
            hair_length="long",
            meche=False,
            estimated_price_cents=10000,
            status=Booking.STATUS_CONFIRMED,
            created_at=timezone.now() - timedelta(days=30),
        )
        self._draft()

        call_command("send_recap_follow_ups")

        notify.assert_called_once()

    @patch(
        "booking.management.commands.send_recap_follow_ups.EmailNotifier.notify",
        return_value=False,
    )
    def test_failed_delivery_is_retried(self, notify):
        draft = self._draft()

        call_command("send_recap_follow_ups")

        draft.refresh_from_db()
        self.assertIsNone(draft.follow_up_sent_at)

    @patch(
        "booking.management.commands.send_recap_follow_ups.EmailNotifier.notify",
        return_value=True,
    )
    def test_generic_recap_is_supported(self, notify):
        marketing_service = MarketingService.objects.create(name="Locks", slug="locks")
        sub_service = MarketingSubService.objects.create(
            service=marketing_service, name="Départ", slug="depart"
        )
        draft = self._draft(
            provider=None,
            payload={
                "requested_marketing_sub_service_id": str(sub_service.id),
                "desired_date": "2026-10-01T14:00",
            },
        )

        call_command("send_recap_follow_ups")

        self.assertIn("recapitulatif-generique", notify.call_args.args[2])
        self.assertIn(str(draft.token), notify.call_args.args[2])
