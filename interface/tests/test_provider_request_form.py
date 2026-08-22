from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from booking.models import Provider, Zone
from interface.forms import GenericBookingRequestForm, ProviderBookingRequestForm


class GenericBookingRequestFormTests(TestCase):
    def test_desired_date_requires_at_least_24_hours_notice(self):
        form = GenericBookingRequestForm(
            data={
                "client_name": "Alice",
                "client_email": "test@example.com",
                "client_phone": "0600000000",
                "desired_date": (timezone.now() + timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M"),
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Le rendez-vous doit être demandé au moins 24 heures à l'avance.",
            form.errors.get("desired_date", []),
        )


class ProviderBookingRequestFormTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(
            name="Divine",
            salon_zone="Paris 10e",
            salon_address="12 rue des Fleurs, 75010 Paris",
        )
        self.zone = Zone.objects.create(name="Toulouse", slug="toulouse")

    def test_invalid_date_format_returns_error(self):
        form = ProviderBookingRequestForm(
            data={
                "service_id": 1,
                "client_name": "Alice",
                "client_email": "test@example.com",
                "location": self.zone.name,
                "location_preference": "domicile",
                "client_address": "5 place du Capitole, 31000 Toulouse",
                "desired_date": "invalid-date",
                "payment_auth_id": "pi_123",
            },
            provider=self.provider,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Merci d'utiliser une date au format JJ/MM/AAAA HH:MM.",
            form.errors.get("desired_date", []),
        )

    def test_missing_location_preference_for_hybrid_provider(self):
        form = ProviderBookingRequestForm(
            data={
                "service_id": 1,
                "client_name": "Alice",
                "client_email": "test@example.com",
                "desired_date": "2026-01-01T12:00",
                "payment_auth_id": "pi_123",
            },
            provider=self.provider,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Merci de choisir si tu préfères venir chez la prestataire ou demander un déplacement.",
            form.non_field_errors(),
        )

    def test_missing_location_for_client_home_provider(self):
        self.provider.location_mode = Provider.LOCATION_MODE_CLIENT_HOME_ONLY
        self.provider.save()

        form = ProviderBookingRequestForm(
            data={
                "service_id": 1,
                "client_name": "Alice",
                "client_email": "test@example.com",
                "location_preference": "domicile",
                "client_address": "5 place du Capitole, 31000 Toulouse",
                "desired_date": "2026-01-01T12:00",
                "payment_auth_id": "pi_123",
            },
            provider=self.provider,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Merci de choisir un lieu.", form.non_field_errors())

    def test_salon_request_no_longer_requires_hair_picture(self):
        form = ProviderBookingRequestForm(
            data={
                "service_id": 1,
                "client_name": "Alice",
                "client_email": "test@example.com",
                "location_preference": "salon",
                "desired_date": "2026-01-01T12:00",
                "payment_auth_id": "pi_123",
            },
            provider=self.provider,
        )

        self.assertTrue(form.is_valid())
