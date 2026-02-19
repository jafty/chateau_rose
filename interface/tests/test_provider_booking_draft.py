from django.test import TestCase
from django.urls import reverse

from booking.models import Provider
from interface.models import ProviderBookingDraft


class ProviderBookingDraftTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Diva")

    def test_creates_draft_with_email_and_payload(self):
        response = self.client.post(
            reverse("interface:provider_booking_draft"),
            data={
                "provider_id": self.provider.id,
                "client_email": "lea@example.com",
                "client_name": "Lea",
                "service_id": "12",
                "desired_date": "2026-02-03T10:00",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProviderBookingDraft.objects.count(), 1)
        draft = ProviderBookingDraft.objects.get()
        self.assertEqual(draft.client_email, "lea@example.com")
        self.assertEqual(draft.payload.get("service_id"), "12")

    def test_updates_existing_draft_from_token(self):
        draft = ProviderBookingDraft.objects.create(
            provider=self.provider,
            client_email="lea@example.com",
            payload={"service_id": "12"},
        )

        response = self.client.post(
            reverse("interface:provider_booking_draft"),
            data={
                "provider_id": self.provider.id,
                "draft_token": str(draft.token),
                "client_email": "lea@example.com",
                "location": "Toulouse",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProviderBookingDraft.objects.count(), 1)
        draft.refresh_from_db()
        self.assertEqual(draft.payload.get("service_id"), "12")
        self.assertEqual(draft.payload.get("location"), "Toulouse")

    def test_rejects_missing_provider(self):
        response = self.client.post(
            reverse("interface:provider_booking_draft"),
            data={"client_email": "lea@example.com"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
