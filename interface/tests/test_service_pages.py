from django.test import TestCase
from django.urls import reverse

from booking.models import Provider, ProviderMarketingService, ProviderZone, Zone
from interface.models import MarketingService, MarketingZone, ServiceRequest


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
        self.provider_a = Provider.objects.create(name="Prestataire A")
        self.provider_b = Provider.objects.create(name="Prestataire B")

        ProviderMarketingService.objects.create(
            provider=self.provider_a, service=self.marketing_service
        )

        ProviderZone.objects.create(provider=self.provider_a, zone=self.toulouse)
        ProviderZone.objects.create(provider=self.provider_a, zone=self.capitole)
        ProviderZone.objects.create(provider=self.provider_b, zone=self.colomiers)

    def test_service_page_filters_providers_by_service(self):
        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_a.name, content)
        self.assertNotIn(self.provider_b.name, content)

    def test_service_city_page_filters_providers_by_service_and_zone(self):
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

    def test_unknown_service_or_zone_returns_404(self):
        service_url = reverse("interface:service_page", args=["unknown-service"])
        city_url = reverse("interface:service_city_page", args=["tresses", "unknown-city"])

        self.assertEqual(self.client.get(service_url).status_code, 404)
        self.assertEqual(self.client.get(city_url).status_code, 404)

    def test_service_page_lists_zone_links(self):
        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("/services/tresses/toulouse", content)

    def test_service_city_district_page_filters_by_zone_slug(self):
        district_url = reverse("interface:service_city_district_page", args=["tresses", "toulouse", "capitole"])
        district_response = self.client.get(district_url)
        self.assertEqual(district_response.status_code, 200)
        district_content = district_response.content.decode()
        self.assertIn(self.provider_a.name, district_content)
        self.assertNotIn(self.provider_b.name, district_content)

    def test_service_page_records_request_even_without_providers(self):
        ProviderMarketingService.objects.all().delete()
        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.post(
            url,
            {
                "request_service": "1",
                "client_name": "Client X",
                "client_phone": "0600000000",
                "location_preference": ServiceRequest.LOCATION_PREFERENCE_SALON,
                "desired_date": "2026-01-10T17:00",
                "details": "Besoin urgent",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ServiceRequest.objects.count(), 1)
        request_record = ServiceRequest.objects.first()
        self.assertEqual(request_record.marketing_service, self.marketing_service)
        self.assertIsNone(request_record.zone)
        self.assertEqual(
            request_record.location_preference, ServiceRequest.LOCATION_PREFERENCE_SALON
        )
        self.assertEqual(
            request_record.desired_date.strftime("%Y-%m-%dT%H:%M"),
            "2026-01-10T17:00",
        )

    def test_salon_only_badge_is_rendered(self):
        self.provider_a.location_mode = Provider.LOCATION_MODE_SALON_ONLY
        self.provider_a.save()

        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Salon</span>", content)
        self.assertNotIn("Salon &amp; domicile", content)

    def test_empty_provider_list_is_hidden(self):
        ProviderMarketingService.objects.all().delete()

        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("Aucun prestataire", content)

    def test_zone_marketing_overrides_are_used(self):
        marketing_zone = MarketingZone.objects.create(
            zone=self.capitole,
            intro="Focus Capitole",
            highlights=["Capitole highlight"],
            hero_image_url="https://cdn.example.com/capitole.jpg",
            meta_description="Meta Capitole",
        )

        url = reverse(
            "interface:service_city_district_page", args=["tresses", "toulouse", "capitole"]
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.marketing_service.intro, content)
        self.assertIn(marketing_zone.intro, content)
        self.assertIn("Rapide", content)
        self.assertIn("Capitole highlight", content)
        self.assertIn(marketing_zone.hero_image_url, content)
