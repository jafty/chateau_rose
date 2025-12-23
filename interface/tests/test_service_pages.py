from django.test import TestCase
from django.urls import reverse

from booking.models import Provider, ProviderZone, Service, Zone


class ServicePagesTests(TestCase):
    def setUp(self):
        self.toulouse = Zone.objects.create(name="Toulouse", slug="toulouse")
        self.colomiers = Zone.objects.create(name="Colomiers", slug="colomiers")

        self.provider_a = Provider.objects.create(name="Prestataire A")
        self.provider_b = Provider.objects.create(name="Prestataire B")

        self.service_tresses_a = Service.objects.create(
            provider=self.provider_a,
            name="Tresses / Braids",
            slug="tresses",
            base_price_cents=5000,
            hair_length_adjustments={},
        )
        self.service_vanilles_b = Service.objects.create(
            provider=self.provider_b,
            name="Vanilles",
            slug="vanilles",
            base_price_cents=6000,
            hair_length_adjustments={},
        )

        ProviderZone.objects.create(provider=self.provider_a, zone=self.toulouse)
        ProviderZone.objects.create(provider=self.provider_b, zone=self.colomiers)

    def test_service_page_filters_providers_by_service(self):
        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_a.name, content)
        self.assertNotIn(self.provider_b.name, content)

    def test_service_city_page_filters_providers_by_service_and_city(self):
        # provider_b offers vanilles; add tresses service but in a different city to validate filtering
        Service.objects.create(
            provider=self.provider_b,
            name="Tresses / Braids",
            slug="tresses",
            base_price_cents=5500,
            hair_length_adjustments={},
        )

        url = reverse("interface:service_city_page", args=["tresses", "toulouse"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_a.name, content)
        self.assertNotIn(self.provider_b.name, content)

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
