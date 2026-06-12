from django.test import TestCase, override_settings


@override_settings(
    MAINTENANCE_MODE=True,
    MAINTENANCE_CONTACT_EMAIL="rdv@example.com",
    MAINTENANCE_RETRY_AFTER_SECONDS=120,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class MaintenanceModeMiddlewareTests(TestCase):
    def test_public_route_shows_maintenance_page(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "120")
        content = response.content.decode()
        self.assertIn("Nous préparons une plus belle expérience", content)
        self.assertIn("Prendre RDV par email", content)
        self.assertIn("mailto:rdv@example.com", content)

    def test_admin_route_is_available_during_maintenance(self):
        response = self.client.get("/admin/")

        self.assertNotEqual(response.status_code, 503)


@override_settings(
    MAINTENANCE_MODE=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class MaintenanceModeDisabledTests(TestCase):
    def test_public_route_uses_regular_site_when_disabled(self):
        response = self.client.get("/")

        self.assertNotEqual(response.status_code, 503)
