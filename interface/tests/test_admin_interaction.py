from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from interface.admin import InteractionAdmin
from interface.models import Interaction


class InteractionAdminTests(TestCase):
    def setUp(self):
        self.model_admin = InteractionAdmin(Interaction, AdminSite())

    def test_contact_prefers_phone_over_email(self):
        interaction = Interaction(contact_phone="+33612345678", contact_email="client@example.com")

        self.assertEqual(self.model_admin.contact(interaction), "+33612345678")

    def test_contact_falls_back_to_email(self):
        interaction = Interaction(contact_phone="", contact_email="client@example.com")

        self.assertEqual(self.model_admin.contact(interaction), "client@example.com")

    def test_contact_returns_dash_when_no_contact_info(self):
        interaction = Interaction(contact_phone="", contact_email="")

        self.assertEqual(self.model_admin.contact(interaction), "-")
