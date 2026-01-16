from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from booking.models import Provider, Zone
from interface.forms import ProviderBookingRequestForm


class ProviderBookingRequestFormTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Divine")
        self.zone = Zone.objects.create(name="Toulouse", slug="toulouse")

    def test_invalid_date_format_returns_error(self):
        form = ProviderBookingRequestForm(
            data={
                "service_id": 1,
                "client_name": "Alice",
                "client_email": "test@example.com",
                "location": self.zone.name,
                "location_preference": "domicile",
                "desired_date": "invalid-date",
                "payment_auth_id": "pi_123",
            },
            files={"current_hair_picture_file": SimpleUploadedFile("current.jpg", b"hair")},
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
            files={"current_hair_picture_file": SimpleUploadedFile("current.jpg", b"hair")},
            provider=self.provider,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Merci de choisir si tu préfères venir au salon ou demander un déplacement.",
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
                "desired_date": "2026-01-01T12:00",
                "payment_auth_id": "pi_123",
            },
            files={"current_hair_picture_file": SimpleUploadedFile("current.jpg", b"hair")},
            provider=self.provider,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Merci de choisir un lieu.", form.non_field_errors())

    def test_missing_current_hair_picture_returns_error(self):
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

        self.assertFalse(form.is_valid())
        self.assertIn("Merci d'ajouter une photo de tes cheveux.", form.non_field_errors())
