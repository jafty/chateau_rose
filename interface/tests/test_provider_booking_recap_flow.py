from datetime import timedelta

from django.core import mail
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.models import (
    Booking,
    Provider,
    ProviderServiceFeeCoupon,
    ProviderZone,
    Service,
    Zone,
)
from interface.models import ProviderBookingDraft


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class ProviderBookingRecapFlowTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(
            name="Diva",
            salon_zone="Toulouse Centre",
            salon_address="12 rue des Fleurs, Toulouse",
            additional_info="Prévoir 10 minutes d'avance.",
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
            "desired_date": (timezone.now() + timedelta(days=7)).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "location_preference": "domicile",
            "location": self.zone.name,
            "client_address": "10 rue de test, Toulouse",
            "hair_length": "long",
            "general_adjustments": '["wash"]',
            "meche": "on",
            "free_text": "Merci de commencer à l'heure 🙏",
        }

    @override_settings(OPERATIONS_EMAIL="ops@example.com")
    def test_create_recap_sends_client_and_operations_emails_and_redirects_to_recap_page(
        self,
    ):
        response = self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data=self._base_payload(),
        )

        draft = ProviderBookingDraft.objects.get(provider=self.provider)
        self.assertRedirects(
            response,
            reverse("interface:provider_booking_recap", args=[draft.token]),
            fetch_redirect_response=False,
        )
        self.assertEqual(draft.client_email, "sarah@example.com")
        self.assertEqual(draft.payload["service_id"], str(self.service.id))
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["sarah@example.com"])
        self.assertIn(str(draft.token), mail.outbox[0].body)
        self.assertEqual(mail.outbox[1].to, ["ops@example.com"])
        self.assertEqual(mail.outbox[1].subject, "Nouveau récapitulatif prestataire")
        self.assertEqual(mail.outbox[1].reply_to, ["sarah@example.com"])
        self.assertIn(str(draft.token), mail.outbox[1].body)
        self.assertIn("Sarah (sarah@example.com)", mail.outbox[1].body)

    def test_domicile_recap_requires_zone_and_preserves_entered_fields(self):
        payload = self._base_payload()
        payload["location"] = ""

        response = self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data=payload,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Merci de choisir une zone pour le rendez-vous à domicile."
        )
        self.assertContains(response, "Sarah")
        self.assertContains(response, "domicile")
        self.assertEqual(ProviderBookingDraft.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_booking_form_rejects_a_date_with_less_than_24_hours_notice(self):
        payload = self._base_payload()
        payload["desired_date"] = (timezone.now() + timedelta(hours=23)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data=payload,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Le rendez-vous doit être demandé au moins 24 heures à l&#x27;avance.",
        )
        self.assertFalse(ProviderBookingDraft.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_create_recap_without_current_hair_picture(self):
        response = self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data=self._base_payload(),
        )

        draft = ProviderBookingDraft.objects.get(provider=self.provider)
        self.assertRedirects(
            response,
            reverse("interface:provider_booking_recap", args=[draft.token]),
            fetch_redirect_response=False,
        )
        self.assertEqual(draft.payload["current_hair_picture"], "")

    def test_recap_page_can_prefill_provider_form_and_complete_booking(self):
        create_response = self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data=self._base_payload(),
        )
        draft = ProviderBookingDraft.objects.get(provider=self.provider)
        self.assertEqual(create_response.status_code, 302)

        recap_page = self.client.get(
            reverse("interface:provider_booking_recap", args=[draft.token])
        )
        self.assertContains(recap_page, "Merci pour ta réservation")
        self.assertContains(recap_page, "Sécuriser ma demande")

        prefill_page = self.client.get(
            reverse("interface:provider_detail", args=[self.provider.id])
            + f"?recap={draft.token}"
        )
        self.assertContains(prefill_page, "Récapitulatif chargé")
        self.assertContains(prefill_page, "Demander mon RDV")

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
        self.assertIn(f"provider_id={self.provider.id}", submission["Location"])

    def test_thank_you_page_displays_provider_additional_info(self):
        response = self.client.get(
            reverse("interface:thank_you_provider_booking")
            + f"?provider={self.provider.name}&provider_id={self.provider.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bon à savoir avant le RDV")
        self.assertContains(response, "Prévoir 10 minutes d'avance.")

    def test_recap_edit_redirects_to_booking_section(self):
        self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data=self._base_payload(),
        )
        draft = ProviderBookingDraft.objects.get(provider=self.provider)

        response = self.client.post(
            reverse("interface:provider_booking_recap", args=[draft.token]),
            data={"action": "edit"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("interface:provider_detail", args=[self.provider.id])
            + f"?recap={draft.token}#booking-wizard",
        )

    def test_recap_includes_service_fee_in_totals_without_coupon(self):
        self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data=self._base_payload(),
        )
        draft = ProviderBookingDraft.objects.get(provider=self.provider)

        recap_page = self.client.get(
            reverse("interface:provider_booking_recap", args=[draft.token])
        )
        self.assertContains(recap_page, "143.75 €")
        self.assertContains(recap_page, "18.75 €")
        self.assertContains(recap_page, "Frais Château Rose à régler")
        self.assertContains(recap_page, "La prestation coiffure est réglée directement")
        self.assertContains(recap_page, "125 €")

    def test_recap_waives_service_fee_with_valid_coupon(self):
        ProviderServiceFeeCoupon.objects.create(provider=self.provider, code="vipzero")
        payload = self._base_payload()
        payload["service_fee_coupon_code"] = "vipzero"
        self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data={
                **payload,
            },
        )
        draft = ProviderBookingDraft.objects.get(provider=self.provider)

        recap_page = self.client.get(
            reverse("interface:provider_booking_recap", args=[draft.token])
        )
        self.assertContains(recap_page, "125 €")
        self.assertContains(recap_page, "0 €")
        self.assertContains(recap_page, "Aucun paiement en ligne requis")
        self.assertContains(recap_page, "Confirmer ma demande")
        self.assertContains(recap_page, "125 €")

    def test_admin_seeded_draft_is_updated_in_place_when_client_completes_prefilled_form(
        self,
    ):
        seeded_date = timezone.now() + timedelta(days=7)
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
                "desired_date": seeded_date.isoformat(),
                "location_preference": "domicile",
                "location": self.zone.name,
                "client_address": "10 rue de test, Toulouse",
                "hair_length": "long",
                "general_adjustments": [],
                "meche": False,
                "free_text": "",
            },
        )
        self.client.force_login(admin_user)

        prefill_page = self.client.get(
            reverse("interface:provider_detail", args=[self.provider.id])
            + f"?recap={seeded.token}"
        )
        self.assertContains(prefill_page, 'data-can-save-partial-prefill="1"')
        self.assertContains(prefill_page, "Enregistrer le brouillon prérempli")

        prefill_page = self.client.get(
            reverse("interface:provider_detail", args=[self.provider.id])
            + f"?recap={seeded.token}"
        )
        self.assertContains(prefill_page, 'data-can-save-partial-prefill="1"')
        self.assertContains(prefill_page, "Enregistrer le brouillon prérempli")

        response = self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data={
                "service_id": self.service.id,
                "client_name": "Nouveau client",
                "client_email": "nouveau@example.com",
                "desired_date": seeded_date.strftime("%Y-%m-%dT%H:%M"),
                "location_preference": "domicile",
                "location": self.zone.name,
                "client_address": "42 avenue des tests, Toulouse",
                "hair_length": "long",
                "general_adjustments": "[]",
                "meche": "",
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
        self.assertEqual(seeded.payload["free_text"], "")

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
            },
        )
        anonymous_prefill_page = self.client.get(
            reverse("interface:provider_detail", args=[self.provider.id])
            + f"?recap={seeded.token}"
        )
        self.assertNotContains(
            anonymous_prefill_page, "Enregistrer le brouillon prérempli"
        )
        self.client.force_login(admin_user)

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
                "recap_token": str(seeded.token),
                "action": "save_prefill",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("interface:provider_detail", args=[self.provider.id])
            + f"?recap={seeded.token}#booking-wizard",
        )
        seeded.refresh_from_db()
        self.assertEqual(seeded.client_name, "")
        self.assertEqual(seeded.client_email, "")
        self.assertEqual(seeded.payload["free_text"], "")
        self.assertEqual(seeded.payload["hair_length"], "long")
