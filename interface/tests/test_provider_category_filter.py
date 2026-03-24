from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.text import slugify

from booking.models import Provider, Service, ServiceCategory


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ProviderCategoryFilterTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(
            name="Amina",
            categorized_services_enabled=True,
        )
        self.first_category = ServiceCategory.objects.create(
            provider=self.provider,
            name="Tresses",
            order=1,
        )
        self.second_category = ServiceCategory.objects.create(
            provider=self.provider,
            name="Locks",
            order=2,
        )
        self.first_service = Service.objects.create(
            provider=self.provider,
            category=self.first_category,
            name="Tresses collées",
            slug="tresses-collees",
            base_price_cents=8000,
        )
        self.second_service = Service.objects.create(
            provider=self.provider,
            category=self.second_category,
            name="Retwist",
            slug="retwist",
            base_price_cents=6500,
        )

    def test_defaults_to_first_category_when_no_querystring(self):
        response = self.client.get(reverse("interface:provider_detail", args=[self.provider.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_category_slug"],
            slugify(self.first_category.name),
        )
        self.assertContains(
            response,
            f'data-service-card="{self.first_service.id}"',
        )
        self.assertNotContains(
            response,
            f'data-service-card="{self.second_service.id}"',
        )

    def test_filters_service_cards_with_category_querystring(self):
        response = self.client.get(
            reverse("interface:provider_detail", args=[self.provider.id]),
            {"category": slugify(self.second_category.name)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_category_slug"],
            slugify(self.second_category.name),
        )
        self.assertContains(
            response,
            f'data-service-card="{self.second_service.id}"',
        )
        self.assertNotContains(
            response,
            f'data-service-card="{self.first_service.id}"',
        )

    def test_service_card_link_keeps_category_and_prefills_service(self):
        selected_slug = slugify(self.second_category.name)
        response = self.client.get(
            reverse("interface:provider_detail", args=[self.provider.id]),
            {"category": selected_slug},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            (
                f'href="?category={selected_slug}&service_id='
                f'{self.second_service.id}#booking-wizard"'
            ),
        )
