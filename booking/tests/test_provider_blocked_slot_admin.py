from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from booking.admin import ProviderBlockedSlotAdmin
from booking.models import Provider, ProviderBlockedSlot


class ProviderBlockedSlotAdminFormTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(
            name="Test Provider",
            description="desc",
            availabilities="9-18",
            contact_phone="0600000000",
            contact_email="provider@example.com",
        )
        self.admin = ProviderBlockedSlotAdmin(ProviderBlockedSlot, AdminSite())

    def test_one_time_block_type_clears_recurring_fields(self):
        form_class = self.admin.get_form(None)
        form = form_class(
            data={
                "provider": self.provider.pk,
                "block_type": "one_time",
                "starts_at_0": "2026-03-10",
                "starts_at_1": "10:00:00",
                "ends_at_0": "2026-03-10",
                "ends_at_1": "12:00:00",
                "weekdays": "0,2,4",
                "starts_time": "09:00:00",
                "ends_time": "18:00:00",
                "recurrence_starts_on": "2026-03-01",
                "recurrence_ends_on": "2026-04-01",
                "source": ProviderBlockedSlot.SOURCE_MANUAL,
                "reason": "indispo ponctuelle",
                "is_active": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()

        self.assertFalse(instance.is_recurring)
        self.assertEqual(instance.weekdays, "")
        self.assertIsNone(instance.starts_time)
        self.assertIsNone(instance.ends_time)
        self.assertIsNone(instance.recurrence_starts_on)
        self.assertIsNone(instance.recurrence_ends_on)

    def test_recurring_block_type_clears_one_time_fields(self):
        form_class = self.admin.get_form(None)
        form = form_class(
            data={
                "provider": self.provider.pk,
                "block_type": "recurring",
                "weekdays": "0,2,4",
                "starts_time": "09:00:00",
                "ends_time": "18:00:00",
                "recurrence_starts_on": "2026-03-01",
                "recurrence_ends_on": "2026-04-01",
                "starts_at_0": "2026-03-10",
                "starts_at_1": "10:00:00",
                "ends_at_0": "2026-03-10",
                "ends_at_1": "12:00:00",
                "source": ProviderBlockedSlot.SOURCE_MANUAL,
                "reason": "indispo hebdo",
                "is_active": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()

        self.assertTrue(instance.is_recurring)
        self.assertIsNone(instance.starts_at)
        self.assertIsNone(instance.ends_at)
