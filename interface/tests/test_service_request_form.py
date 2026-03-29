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
                "contact": "06 12 34 56 78",
                "availabilities": ["weekday_morning", "weekend_afternoon"],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_requires_service_contact_and_availabilities(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": "",
                "contact": "",
                "availabilities": [],
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("marketing_service", form.errors)
        self.assertIn("contact", form.errors)
        self.assertIn("availabilities", form.errors)

    def test_sanitizes_whatsapp_number(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": self.service.id,
                "contact": "06 12 34 56 78",
                "availabilities": ["weekday_evening"],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()
        self.assertEqual(instance.client_phone, "0612345678")
        self.assertEqual(instance.client_email, "")
        self.assertEqual(instance.availabilities, ["weekday_evening"])

    def test_accepts_email_contact(self):
        form = ServiceRequestForm(
            data={
                "marketing_service": self.service.id,
                "contact": "test@example.com",
                "availabilities": ["weekend_morning"],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()
        self.assertEqual(instance.client_email, "test@example.com")
        self.assertEqual(instance.client_phone, "")
