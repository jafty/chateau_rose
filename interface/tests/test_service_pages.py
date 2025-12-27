from django.test import TestCase
from django.urls import reverse

from booking.models import Provider, ProviderMarketingService, ProviderZone, Zone
from interface.models import (
    MarketingCity,
    MarketingDistrict,
    MarketingService,
    MarketingServiceCity,
)


class ServicePagesTests(TestCase):
    def setUp(self):
        self.toulouse = Zone.objects.create(name="Toulouse", slug="toulouse")
        self.capitole = Zone.objects.create(name="Capitole", slug="capitole")
        self.colomiers = Zone.objects.create(name="Colomiers", slug="colomiers")

        self.marketing_service = MarketingService.objects.create(
            name="Tresses / Braids",
            slug="tresses",
            intro="Intro tresses",
            highlights=["Rapide", "Soigné"],
        )
        self.marketing_city = MarketingCity.objects.create(
            name="Toulouse",
            slug="toulouse",
            intro="Ville rose",
        )
        self.marketing_district = MarketingDistrict.objects.create(
            city=self.marketing_city,
            name="Capitole",
            slug="capitole",
        )

        self.provider_a = Provider.objects.create(name="Prestataire A")
        self.provider_b = Provider.objects.create(name="Prestataire B")

        ProviderMarketingService.objects.create(
            provider=self.provider_a, service=self.marketing_service
        )

        ProviderZone.objects.create(provider=self.provider_a, zone=self.capitole)
        ProviderZone.objects.create(provider=self.provider_b, zone=self.colomiers)

    def test_service_page_filters_providers_by_service(self):
        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_a.name, content)
        self.assertNotIn(self.provider_b.name, content)

    def test_service_city_page_filters_providers_by_service_and_city(self):
        ProviderMarketingService.objects.create(
            provider=self.provider_b, service=self.marketing_service
        )

        url = reverse("interface:service_city_page", args=["tresses", "toulouse"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_a.name, content)
        self.assertNotIn(self.provider_b.name, content)

    def test_service_page_renders_marketing_copy(self):
        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Intro tresses", content)
        self.assertIn("Rapide", content)

    def test_service_page_uses_static_main_image_when_no_upload(self):
        self.marketing_service.main_image_url = "https://static.example.com/tresses.jpg"
        self.marketing_service.save()

        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("https://static.example.com/tresses.jpg", response.content.decode())

    def test_service_city_page_prefers_city_override_copy(self):
        MarketingServiceCity.objects.create(
            service=self.marketing_service,
            city=self.marketing_city,
            intro="Intro Toulouse spécifique",
            highlights=["Point local"],
        )

        url = reverse("interface:service_city_page", args=["tresses", "toulouse"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Intro Toulouse spécifique", content)
        self.assertIn("Point local", content)
        self.assertNotIn("Intro tresses", content)

    def test_service_city_page_falls_back_with_city_context_when_no_override(self):
        url = reverse("interface:service_city_page", args=["tresses", "toulouse"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Toulouse", content)
        self.assertIn("Intro tresses", content)

    def test_unknown_service_or_city_returns_404(self):
        service_url = reverse("interface:service_page", args=["unknown-service"])
        city_url = reverse("interface:service_city_page", args=["tresses", "unknown-city"])

        self.assertEqual(self.client.get(service_url).status_code, 404)
        self.assertEqual(self.client.get(city_url).status_code, 404)

    def test_service_page_lists_city_links(self):
        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Should list at least Toulouse link
        self.assertIn("/services/tresses/toulouse", content)

    def test_service_city_page_lists_district_links_and_filters_district(self):
        url = reverse("interface:service_city_page", args=["tresses", "toulouse"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("/services/tresses/toulouse/capitole", content)

        district_url = reverse("interface:service_city_district_page", args=["tresses", "toulouse", "capitole"])
        district_response = self.client.get(district_url)
        self.assertEqual(district_response.status_code, 200)
        district_content = district_response.content.decode()
        self.assertIn(self.provider_a.name, district_content)
        self.assertNotIn(self.provider_b.name, district_content)
