from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from booking.models import Provider
from interface.admin import ProviderBookingDraftAdmin
from interface.models import ProviderBookingDraft


class ProviderBookingDraftAdminTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Admin Draft Provider")
        self.admin_user = get_user_model().objects.create_user(
            username="staff_admin_draft",
            email="staff@example.com",
            password="password123",
            is_staff=True,
        )
        self.admin = ProviderBookingDraftAdmin(ProviderBookingDraft, AdminSite())
        self.factory = RequestFactory()

    def test_save_model_sets_created_by_for_admin_source(self):
        request = self.factory.post("/admin/interface/providerbookingdraft/add/")
        request.user = self.admin_user
        draft = ProviderBookingDraft(
            provider=self.provider,
            source=ProviderBookingDraft.SOURCE_ADMIN,
            client_name="Lead",
            client_email="lead@example.com",
            payload={"client_name": "Lead", "client_email": "lead@example.com"},
        )

        self.admin.save_model(request, draft, form=None, change=False)

        draft.refresh_from_db()
        self.assertEqual(draft.created_by, self.admin_user)
