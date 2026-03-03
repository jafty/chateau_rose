from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase, override_settings

from interface.admin import ServiceRequestAdmin
from interface.models import ServiceRequest


class ServiceRequestAdminTests(TestCase):
    def test_admin_get_form_does_not_raise_for_non_editable_created_at(self):
        request = RequestFactory().get('/admin/interface/servicerequest/1/change/')
        model_admin = ServiceRequestAdmin(ServiceRequest, AdminSite())

        form_class = model_admin.get_form(request)

        self.assertIsNotNone(form_class)
        self.assertNotIn('created_at', form_class.base_fields)

    @override_settings(MEDIA_URL='/media/')
    def test_resolve_inspiration_url_prefixes_relative_path_with_media_url(self):
        model_admin = ServiceRequestAdmin(ServiceRequest, AdminSite())

        resolved = model_admin._resolve_inspiration_url('bookings/inspiration/IMG_8662.jpg')

        self.assertEqual(resolved, '/media/bookings/inspiration/IMG_8662.jpg')

    @override_settings(MEDIA_URL='/media/')
    def test_resolve_inspiration_url_keeps_absolute_url(self):
        model_admin = ServiceRequestAdmin(ServiceRequest, AdminSite())

        original = 'https://cdn.example.com/bookings/inspiration/IMG_8662.jpg'
        resolved = model_admin._resolve_inspiration_url(original)

        self.assertEqual(resolved, original)
