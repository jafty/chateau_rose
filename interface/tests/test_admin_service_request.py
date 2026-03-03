from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from interface.admin import ServiceRequestAdmin
from interface.models import ServiceRequest


class ServiceRequestAdminTests(TestCase):
    def test_admin_get_form_does_not_raise_for_non_editable_created_at(self):
        request = RequestFactory().get('/admin/interface/servicerequest/1/change/')
        model_admin = ServiceRequestAdmin(ServiceRequest, AdminSite())

        form_class = model_admin.get_form(request)

        self.assertIsNotNone(form_class)
        self.assertNotIn('created_at', form_class.base_fields)
