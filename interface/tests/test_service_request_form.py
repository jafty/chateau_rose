from django.test import TestCase

from interface.forms import ServiceRequestForm
from interface.models import MarketingService


class ServiceRequestFormTests(TestCase):
    def setUp(self):
        self.service = MarketingService.objects.create(name="Tresses", slug="tresses")

    def test_requires_minimal_fields(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": self.service.id,
                "client_phone": "06 12 34 56 78",
                "details": "Knotless braids taille S.",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_requires_details_and_phone(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": "",
                "client_phone": "",
                "details": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("marketing_service", form.errors)
        self.assertIn("client_phone", form.errors)
        self.assertIn("details", form.errors)

    def test_sanitizes_whatsapp_number(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": self.service.id,
                "client_phone": "06 12 34 56 78",
                "details": "Vanilles à domicile",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()
        self.assertEqual(instance.client_phone, "0612345678")
        self.assertEqual(instance.availabilities, [])

    def test_phone_is_required(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": self.service.id,
                "client_phone": "",
                "details": "Vanilles à domicile",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("client_phone", form.errors)
