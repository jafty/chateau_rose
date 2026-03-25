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

    def _build_request(self):
        request = self.factory.post("/admin/booking/provider/")
        request.user = self.staff_user
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_generate_lead_prefill_links_creates_admin_draft_and_message(self):
        request = self._build_request()

        self.admin.generate_lead_prefill_links(request, Provider.objects.filter(id=self.provider.id))

        draft = ProviderBookingDraft.objects.get(provider=self.provider)
        self.assertEqual(draft.source, ProviderBookingDraft.SOURCE_ADMIN)
        self.assertEqual(draft.created_by, self.staff_user)
        self.assertEqual(draft.payload["service_id"], "")
        self.assertEqual(draft.payload["general_adjustments"], [])
        self.assertEqual(draft.payload["inspiration_pictures"], [])

        messages = [str(message) for message in request._messages]
        self.assertEqual(len(messages), 1)
        expected_link = f"/prestataires/{self.provider.id}/?recap={draft.token}#booking-wizard"
        self.assertIn(expected_link, messages[0])
