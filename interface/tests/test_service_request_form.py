from django.test import TestCase

from interface.forms import ServiceRequestForm
from interface.models import MarketingService, ServiceRequest


class ServiceRequestFormTests(TestCase):
    def setUp(self):
        self.service = MarketingService.objects.create(name="Tresses", slug="tresses")

    def test_requires_salon_area_for_salon_requests(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": self.service.id,
                "location_preference": ServiceRequest.LOCATION_PREFERENCE_SALON,
                "desired_date": "2026-01-10T17:00",
                "client_name": "Client X",
                "client_phone": "+33612345678",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("salon_area", form.errors)

    def test_accepts_whatsapp_and_persists_availabilities(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": self.service.id,
                "location_preference": ServiceRequest.LOCATION_PREFERENCE_CLIENT_HOME,
                "desired_date": "2026-01-10T17:00",
                "client_name": "Client X",
                "client_phone": "06 12 34 56 78",
                "availabilities": ["morning", "weekend"],
                "hair_length": "epaule",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()
        self.assertEqual(instance.client_phone, "0612345678")
        self.assertEqual(instance.availabilities, ["morning", "weekend"])
