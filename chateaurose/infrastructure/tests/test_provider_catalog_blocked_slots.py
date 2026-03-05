from datetime import datetime, timezone

from django.test import TestCase

from booking.models import Provider, ProviderBlockedSlot
from chateaurose.infrastructure.provider_catalog import DjangoProviderCatalog


class ProviderCatalogBlockedSlotsTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Maison Test")
        self.catalog = DjangoProviderCatalog()

    def test_provider_has_blocked_slot_with_one_time_slot(self):
        ProviderBlockedSlot.objects.create(
            provider=self.provider,
            starts_at=datetime(2026, 1, 12, 18, 30, tzinfo=timezone.utc),
            ends_at=datetime(2026, 1, 12, 22, 0, tzinfo=timezone.utc),
            is_recurring=False,
        )

        has_block = self.catalog.provider_has_blocked_slot(
            str(self.provider.id),
            "2026-01-12T19:00:00Z",
        )

        assert has_block is True

    def test_provider_has_blocked_slot_with_weekly_recurring_days(self):
        ProviderBlockedSlot.objects.create(
            provider=self.provider,
            is_recurring=True,
            weekdays="0,1,2,3,4,5,6",
            starts_time="18:30",
            ends_time="22:00",
        )

        has_block = self.catalog.provider_has_blocked_slot(
            str(self.provider.id),
            "2026-01-13T19:00:00Z",
        )

        assert has_block is True

    def test_provider_has_blocked_slot_with_weekend_recurring_days(self):
        ProviderBlockedSlot.objects.create(
            provider=self.provider,
            is_recurring=True,
            weekdays="5,6",
            starts_time="10:00",
            ends_time="22:00",
        )

        saturday_blocked = self.catalog.provider_has_blocked_slot(
            str(self.provider.id),
            "2026-01-17T11:00:00Z",
        )
        monday_blocked = self.catalog.provider_has_blocked_slot(
            str(self.provider.id),
            "2026-01-19T11:00:00Z",
        )

        assert saturday_blocked is True
        assert monday_blocked is False
