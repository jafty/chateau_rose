from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from booking.models import Booking, Provider, ProviderZone, Service, Zone
from interface.models import ProviderBookingDraft


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ProviderBookingRecapFlowTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(
            name="Diva",
            salon_zone="Toulouse Centre",
            salon_address="12 rue des Fleurs, Toulouse",
        )
        self.zone = Zone.objects.create(name="Toulouse", slug="toulouse")
        ProviderZone.objects.create(provider=self.provider, zone=self.zone)
        self.service = Service.objects.create(
            provider=self.provider,
            name="Knotless",
            slug="knotless",
            base_price_cents=9000,
            hair_length_adjustments={"medium": 0, "long": 1500},
            general_adjustments={"wash": 500},
            meche_bonus_cents=1500,
        )

    def _base_payload(self):
        return {
            "service_id": self.service.id,
            "client_name": "Sarah",
            "client_email": "sarah@example.com",
            "desired_date": "2026-04-01T10:30",
            "location_preference": "domicile",
            "location": self.zone.name,
            "client_address": "10 rue de test, Toulouse",
            "hair_length": "long",
            "general_adjustments": '["wash"]',
            "meche": "on",
            "free_text": "Merci de commencer à l'heure 🙏",
        }

    def test_create_recap_sends_email_and_redirects_to_recap_page(self):
        response = self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data={
                **self._base_payload(),
                "current_hair_picture_file": SimpleUploadedFile("current.jpg", b"hair"),
            },
        )

        draft = ProviderBookingDraft.objects.get(provider=self.provider)
        self.assertRedirects(
            response,
            reverse("interface:provider_booking_recap", args=[draft.token]),
            fetch_redirect_response=False,
        )
        self.assertEqual(draft.client_email, "sarah@example.com")
        self.assertEqual(draft.payload["service_id"], str(self.service.id))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(draft.token), mail.outbox[0].body)

    def test_recap_page_can_prefill_provider_form_and_complete_booking(self):
        create_response = self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data={
                **self._base_payload(),
                "current_hair_picture_file": SimpleUploadedFile("current.jpg", b"hair"),
            },
        )
        draft = ProviderBookingDraft.objects.get(provider=self.provider)
        self.assertEqual(create_response.status_code, 302)

        recap_page = self.client.get(reverse("interface:provider_booking_recap", args=[draft.token]))
        self.assertContains(recap_page, "Vérifie ton récapitulatif")
        self.assertContains(recap_page, "Sécuriser ce créneau")

        prefill_page = self.client.get(
            reverse("interface:provider_detail", args=[self.provider.id]) + f"?recap={draft.token}"
        )
        self.assertContains(prefill_page, "Récapitulatif chargé")
        self.assertContains(prefill_page, "Voir mon récapitulatif")

        submission = self.client.post(
            reverse("interface:provider_booking_recap", args=[draft.token]),
            data={
                "action": "confirm",
                "payment_auth_id": "auth_test_1",
            },
        )

        self.assertEqual(submission.status_code, 302)
        self.assertEqual(Booking.objects.count(), 1)
        draft.refresh_from_db()
        self.assertIsNotNone(draft.completed_at)
