from django.contrib.auth import get_user_model
from django.core import signing
from django.test import RequestFactory, TestCase, override_settings


@override_settings(
    MAINTENANCE_MODE=True,
    MAINTENANCE_CONTACT_EMAIL="rdv@example.com",
    MAINTENANCE_RETRY_AFTER_SECONDS=120,
    MAINTENANCE_PREVIEW_COOKIE_MAX_AGE_SECONDS=3600,
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
        self.assertEqual(
            response.headers["Cache-Control"],
            "no-store, no-cache, must-revalidate, max-age=0",
        )
        self.assertEqual(response.headers["Pragma"], "no-cache")

    def test_admin_route_is_available_during_maintenance(self):
        response = self.client.get("/admin/")

        self.assertNotEqual(response.status_code, 503)

    def test_admin_user_can_preview_public_site_during_maintenance(self):
        user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertNotEqual(response.status_code, 503)

    def test_non_admin_user_still_sees_maintenance_page(self):
        user = get_user_model().objects.create_user(
            username="client",
            email="client@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 503)

    def test_admin_route_sets_preview_cookie_for_admin_user(self):
        user = get_user_model().objects.create_superuser(
            username="preview-admin",
            email="preview-admin@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get("/admin/")

        self.assertIn("maintenance_preview", response.cookies)

    def test_signed_preview_cookie_can_preview_public_site(self):
        self.client.cookies["maintenance_preview"] = signing.dumps(
            {"preview": "admin"},
            salt="chateaurose.maintenance-preview",
        )

        response = self.client.get("/")

        self.assertNotEqual(response.status_code, 503)

    def test_invalid_preview_cookie_still_sees_maintenance_page(self):
        self.client.cookies["maintenance_preview"] = "invalid"

        response = self.client.get("/")

        self.assertEqual(response.status_code, 503)

    def test_favicon_is_available_during_maintenance(self):
        response = self.client.get("/favicon.ico")

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], "/static/assets/cr_logo.svg")

    def test_request_without_session_shows_maintenance_page(self):
        from chateaurose.middleware import MaintenanceModeMiddleware

        request = RequestFactory().get("/")
        middleware = MaintenanceModeMiddleware(lambda _request: None)

        response = middleware(request)

        self.assertEqual(response.status_code, 503)


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
