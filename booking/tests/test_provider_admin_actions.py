from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from booking.admin import ProviderAdmin
from booking.models import Provider
from interface.models import ProviderBookingDraft


class ProviderAdminActionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.provider = Provider.objects.create(name="Diva Action")
        self.admin = ProviderAdmin(Provider, AdminSite())
        self.staff_user = get_user_model().objects.create_user(
            username="staff_provider_admin",
            email="staff-provider@example.com",
            password="password123",
            is_staff=True,
        )

    def _build_request(self, path="/admin/booking/provider/", data=None):
        request = self.factory.post(path, data=data or {})
        request.user = self.staff_user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_generate_lead_prefill_links_redirects_to_prefill_page(self):
        request = self._build_request()

        response = self.admin.generate_lead_prefill_links(
            request, Provider.objects.filter(id=self.provider.id)
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            f"/admin/booking/provider/{self.provider.id}/generate-lead-prefill-link/",
            response.url,
        )
        self.assertEqual(ProviderBookingDraft.objects.count(), 0)

    def test_generate_lead_prefill_link_view_creates_draft_with_prefill_payload(self):
        service = self.provider.services.create(
            name="Knotless",
            slug="knotless-test-admin-action",
            base_price_cents=9000,
            hair_length_adjustments={"long": 1200},
            general_adjustments={"wash": 500},
            meche_bonus_cents=1500,
        )

        request = self._build_request(
            path=f"/admin/booking/provider/{self.provider.id}/generate-lead-prefill-link/",
            data={
            "service": str(service.id),
            "desired_date": "2026-06-01T10:30",
            "hair_length": "long",
            "general_adjustments": '["wash"]',
            "meche": "on",
            "location_preference": "domicile",
            "location": "Toulouse Centre",
            "client_address": "10 rue des tests",
            "free_text": "Lead phone request",
            "client_name": "Lead Name",
            "client_email": "lead@example.com",
            },
        )

        response = self.admin.generate_lead_prefill_link_view(request, self.provider.id)

        self.assertEqual(response.status_code, 200)
        draft = ProviderBookingDraft.objects.get(provider=self.provider)
        self.assertEqual(draft.source, ProviderBookingDraft.SOURCE_ADMIN)
        self.assertEqual(draft.created_by, self.staff_user)
        self.assertEqual(draft.payload["service_id"], str(service.id))
        self.assertEqual(draft.payload["service_name"], "Knotless")
        self.assertEqual(draft.payload["hair_length"], "long")
        self.assertEqual(draft.payload["general_adjustments"], ["wash"])
        self.assertTrue(draft.payload["meche"])
        self.assertEqual(draft.payload["client_name"], "Lead Name")
        self.assertEqual(draft.payload["client_email"], "lead@example.com")
        self.assertIn(f"?recap={draft.token}#booking-wizard", response.context_data["generated_link"])
