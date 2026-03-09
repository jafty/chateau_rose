from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.utils import timezone

from booking.models import Provider, Service
from interface.admin import QuickCheckoutPageAdmin
from interface.models import QuickCheckoutPage


class QuickCheckoutPageAdminFormTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Diva", salon_zone="Paris")
        self.service = Service.objects.create(
            provider=self.provider,
            name="Tresses",
            slug="tresses-admin",
            base_price_cents=5000,
        )
        self.checkout = QuickCheckoutPage.objects.create(
            provider=self.provider,
            service=self.service,
            client_name="Léa",
            client_email="lea@example.com",
            desired_date=timezone.now() + timedelta(days=2),
            location_preference="salon",
            final_price_cents=12000,
            reservation_fee_cents=3000,
        )
        self.admin = QuickCheckoutPageAdmin(QuickCheckoutPage, AdminSite())

    def test_form_prefills_provider_salon_zone(self):
        form_class = self.admin.get_form(None, self.checkout)
        form = form_class(instance=self.checkout)

        self.assertEqual(form.fields["provider_salon_zone"].initial, "Paris")

    def test_form_requires_provider_salon_zone_for_salon_location(self):
        form_class = self.admin.get_form(None, self.checkout)
        form = form_class(
            data={
                "provider": self.provider.id,
                "service": self.service.id,
                "client_name": "Léa",
                "client_email": "lea@example.com",
                "desired_date_0": (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
                "desired_date_1": "10:30:00",
                "location_preference": "salon",
                "provider_salon_zone": "",
                "client_address": "",
                "free_text": "",
                "final_price_cents": 12000,
                "reservation_fee_cents": 3000,
                "is_active": "on",
            },
            instance=self.checkout,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("provider_salon_zone", form.errors)

    def test_form_accepts_salon_booking_when_provider_zone_is_filled_in_form(self):
        self.provider.salon_zone = ""
        self.provider.save(update_fields=["salon_zone"])

        form_class = self.admin.get_form(None, self.checkout)
        form = form_class(
            data={
                "provider": self.provider.id,
                "service": self.service.id,
                "client_name": "Léa",
                "client_email": "lea@example.com",
                "desired_date_0": (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
                "desired_date_1": "10:30:00",
                "location_preference": "salon",
                "provider_salon_zone": "Toulouse centre",
                "client_address": "",
                "free_text": "",
                "final_price_cents": 12000,
                "reservation_fee_cents": 3000,
                "is_active": "on",
            },
            instance=self.checkout,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_updates_provider_salon_zone(self):
        form_class = self.admin.get_form(None, self.checkout)
        form = form_class(
            data={
                "provider": self.provider.id,
                "service": self.service.id,
                "client_name": "Léa",
                "client_email": "lea@example.com",
                "desired_date_0": (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
                "desired_date_1": "10:30:00",
                "location_preference": "salon",
                "provider_salon_zone": "Blagnac",
                "client_address": "",
                "free_text": "",
                "final_price_cents": 12000,
                "reservation_fee_cents": 3000,
                "is_active": "on",
            },
            instance=self.checkout,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.salon_zone, "Blagnac")
