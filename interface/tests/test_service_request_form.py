from django.test import TestCase

from interface.forms import ServiceRequestForm
from interface.models import MarketingService, ServiceRequest


class ServiceRequestFormTests(TestCase):
    def setUp(self):
        self.service = MarketingService.objects.create(name="Tresses", slug="tresses")

    def test_requires_minimal_fields(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": self.service.id,
                "location_preference": ServiceRequest.LOCATION_PREFERENCE_SALON,
                "client_phone": "+33612345678",
                "details": "Knotless braids taille S.",
                "availabilities": ["weekday_evening"],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_requires_details_and_availabilities(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": self.service.id,
                "location_preference": ServiceRequest.LOCATION_PREFERENCE_CLIENT_HOME,
                "client_phone": "06 12 34 56 78",
                "details": "",
                "availabilities": [],
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("details", form.errors)
        self.assertIn("availabilities", form.errors)

    def test_sanitizes_whatsapp_number(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": self.service.id,
                "location_preference": ServiceRequest.LOCATION_PREFERENCE_CLIENT_HOME,
                "client_phone": "06 12 34 56 78",
                "details": "Vanilles à domicile",
                "availabilities": ["weekday_morning", "weekend_morning"],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()
        self.assertEqual(instance.client_phone, "0612345678")
        self.assertEqual(instance.availabilities, ["weekday_morning", "weekend_morning"])
