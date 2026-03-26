from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
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

    def test_recap_edit_redirects_to_booking_section(self):
        self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data={
                **self._base_payload(),
                "current_hair_picture_file": SimpleUploadedFile("current.jpg", b"hair"),
            },
        )
        draft = ProviderBookingDraft.objects.get(provider=self.provider)

        response = self.client.post(
            reverse("interface:provider_booking_recap", args=[draft.token]),
            data={"action": "edit"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("interface:provider_detail", args=[self.provider.id]) + f"?recap={draft.token}#booking-wizard",
        )

    def test_admin_seeded_draft_is_updated_in_place_when_client_completes_prefilled_form(self):
        admin_user = get_user_model().objects.create_user(
            username="admin_draft_user",
            email="admin@example.com",
            password="test12345",
            is_staff=True,
        )
        seeded = ProviderBookingDraft.objects.create(
            provider=self.provider,
            source=ProviderBookingDraft.SOURCE_ADMIN,
            created_by=admin_user,
            client_name="",
            client_email="",
            payload={
                "service_id": str(self.service.id),
                "service_name": self.service.name,
                "client_name": "",
                "client_email": "",
                "desired_date": "2026-04-02T10:00:00+00:00",
                "location_preference": "domicile",
                "location": self.zone.name,
                "client_address": "10 rue de test, Toulouse",
                "hair_length": "long",
                "general_adjustments": [],
                "meche": False,
                "free_text": "",
                "current_hair_picture": "",
                "inspiration_pictures": [],
            },
        )

        prefill_page = self.client.get(
            reverse("interface:provider_detail", args=[self.provider.id]) + f"?recap={seeded.token}"
        )
        self.assertContains(prefill_page, 'data-can-save-partial-prefill="1"')
        self.assertContains(prefill_page, "Enregistrer le brouillon prérempli")

        response = self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data={
                "service_id": self.service.id,
                "client_name": "Nouveau client",
                "client_email": "nouveau@example.com",
                "desired_date": "2026-04-03T11:30",
                "location_preference": "domicile",
                "location": self.zone.name,
                "client_address": "42 avenue des tests, Toulouse",
                "hair_length": "long",
                "general_adjustments": "[]",
                "meche": "",
                "free_text": "Infos admin draft",
                "current_hair_picture_file": SimpleUploadedFile("current.jpg", b"hair"),
                "recap_token": str(seeded.token),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("interface:provider_booking_recap", args=[seeded.token]),
        )
        self.assertEqual(ProviderBookingDraft.objects.count(), 1)
        seeded.refresh_from_db()
        self.assertEqual(seeded.source, ProviderBookingDraft.SOURCE_ADMIN)
        self.assertEqual(seeded.client_name, "Nouveau client")
        self.assertEqual(seeded.client_email, "nouveau@example.com")
        self.assertEqual(seeded.payload["free_text"], "Infos admin draft")

    def test_admin_can_save_partial_prefill_without_client_identity_or_pictures(self):
        admin_user = get_user_model().objects.create_user(
            username="admin_partial_prefill_user",
            email="admin-partial@example.com",
            password="test12345",
            is_staff=True,
        )
        seeded = ProviderBookingDraft.objects.create(
            provider=self.provider,
            source=ProviderBookingDraft.SOURCE_ADMIN,
            created_by=admin_user,
            client_name="",
            client_email="",
            payload={
                "service_id": str(self.service.id),
                "service_name": self.service.name,
                "client_name": "",
                "client_email": "",
                "desired_date": "",
                "location_preference": "",
                "location": "",
                "client_address": "",
                "hair_length": "",
                "general_adjustments": [],
                "meche": False,
                "free_text": "",
                "current_hair_picture": "",
                "inspiration_pictures": [],
            },
        )

        response = self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data={
                "service_id": self.service.id,
                "client_name": "",
                "client_email": "",
                "desired_date": "",
                "location_preference": "",
                "location": "",
                "client_address": "",
                "hair_length": "long",
                "general_adjustments": "[]",
                "meche": "",
                "free_text": "Lead WhatsApp: disponible vendredi",
                "recap_token": str(seeded.token),
                "action": "save_prefill",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("interface:provider_detail", args=[self.provider.id]) + f"?recap={seeded.token}#booking-wizard",
        )
        seeded.refresh_from_db()
        self.assertEqual(seeded.client_name, "")
        self.assertEqual(seeded.client_email, "")
        self.assertEqual(seeded.payload["free_text"], "Lead WhatsApp: disponible vendredi")
        self.assertEqual(seeded.payload["hair_length"], "long")
