from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from booking.models import Provider, Service
from interface.models import MarketingService, MarketingSubService


@override_settings(DEBUG=False, STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage", STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class BookingFormStartedAnalyticsRenderTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(
            name="Rose Stylist",
            description="Braids",
            is_visible_on_website=True,
            salon_zone="Toulouse Centre",
            salon_address="1 rue Rose",
            location_mode=Provider.LOCATION_MODE_HYBRID,
        )
        Service.objects.create(provider=self.provider, name="Tresses", base_price_cents=5000)
        self.service = MarketingService.objects.create(name="Tresses", slug="tresses")
        self.sub_service = MarketingSubService.objects.create(
            service=self.service,
            name="Tresses plaquées",
            slug="tresses-plaquees",
            is_visible=True,
            generic_booking_enabled=True,
            generic_base_price_cents=12000,
        )

    def test_provider_booking_form_exposes_stable_enabled_analytics_marker_for_customers(self):
        response = self.client.get(reverse("interface:provider_detail", args=[self.provider.id]))

        self.assertContains(response, 'data-analytics-booking-form')
        self.assertContains(response, 'data-analytics-enabled="true"')
        self.assertContains(response, 'data-analytics-stylist-selected="true"')
        self.assertContains(response, 'data-analytics-booking-flow-version="provider_standard_v1"')

    def test_generic_booking_form_exposes_safe_context_properties(self):
        response = self.client.get(reverse("interface:sub_service_page", args=[self.service.slug, self.sub_service.slug]))

        self.assertContains(response, 'id="generic-request-form"')
        self.assertContains(response, 'data-analytics-booking-form')
        self.assertContains(response, 'data-analytics-service-slug="tresses-plaquees"')
        self.assertContains(response, 'data-analytics-service-category="tresses"')
        self.assertContains(response, 'data-analytics-stylist-selected="false"')
        self.assertContains(response, 'data-analytics-booking-flow-version="generic_sub_service_v1"')

    def test_staff_sessions_do_not_expose_enabled_tracker(self):
        user = get_user_model().objects.create_user(
            username="staff", email="staff@example.com", password="test", is_staff=True
        )
        self.client.force_login(user)

        response = self.client.get(reverse("interface:provider_detail", args=[self.provider.id]))

        self.assertContains(response, 'data-analytics-booking-form')
        self.assertContains(response, 'data-analytics-enabled="false"')
        self.assertNotContains(response, 'booking-form-start-tracker.js')

    def test_explicit_session_exclusion_disables_tracker(self):
        session = self.client.session
        session["analytics_excluded"] = True
        session.save()

        response = self.client.get(reverse("interface:provider_detail", args=[self.provider.id]))

        self.assertContains(response, 'data-analytics-enabled="false"')

    @override_settings(DEBUG=True)
    def test_local_development_disables_tracker(self):
        response = self.client.get(reverse("interface:provider_detail", args=[self.provider.id]))

        self.assertContains(response, 'data-analytics-enabled="false"')
