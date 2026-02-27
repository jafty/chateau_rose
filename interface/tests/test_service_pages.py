from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from booking.models import Provider, ProviderMarketingService, ProviderZone, Zone
from interface.models import ClientReview, MarketingService, MarketingServiceZone, MarketingZone, ServiceRequest


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
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
            short_intro="Intro courte tresses",
            long_description="Description longue tresses",
            long_title="Titre long tresses",
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

        MarketingZone.objects.create(zone=self.toulouse)

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
        self.assertIn("Intro courte tresses", content)
        self.assertIn("Titre long tresses", content)
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
        self.assertNotIn("/services/tresses/capitole", content)

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
                "client_email": "test@example.com",
                "location_preference": ServiceRequest.LOCATION_PREFERENCE_SALON,
                "desired_date": "2026-01-10T17:00",
                "hair_length": "Épaules",
                "meche_provided": "on",
                "details": "Besoin urgent",
                "inspiration_pictures": [
                    SimpleUploadedFile("insp.jpg", b"hair", content_type="image/jpeg")
                ],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].endswith("?anchor=service-request"))
        self.assertEqual(ServiceRequest.objects.count(), 1)
        request_record = ServiceRequest.objects.first()
        self.assertEqual(request_record.marketing_service, self.marketing_service)
        self.assertIsNone(request_record.zone)
        self.assertEqual(
            request_record.location_preference, ServiceRequest.LOCATION_PREFERENCE_SALON
        )
        self.assertEqual(request_record.desired_date.strftime("%Y-%m-%d"), "2026-01-10")
        self.assertEqual(request_record.hair_length, "Épaules")
        self.assertTrue(request_record.meche_provided)
        self.assertEqual(len(request_record.inspiration_picture_urls), 1)

    def test_home_displays_featured_review(self):
        ClientReview.objects.create(
            client_name="Awa",
            review_text="Super expérience.",
            rating=5,
            is_featured=False,
            is_active=True,
        )
        ClientReview.objects.create(
            client_name="Mina",
            review_text="Service nickel.",
            rating=5,
            is_featured=True,
            is_active=True,
        )

        response = self.client.get(reverse("interface:home"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Service nickel.", content)


    def test_home_renders_video_review_media(self):
        ClientReview.objects.create(
            client_name="Awa",
            review_text="Super expérience.",
            media_kind=ClientReview.MEDIA_VIDEO,
            video_url="https://cdn.example.com/reviews/story.mp4",
            rating=5,
            is_featured=True,
            is_active=True,
        )

        response = self.client.get(reverse("interface:home"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("<video", content)
        self.assertIn("story-media-badge", content)
        self.assertIn('data-story-media-kind="video"', content)
        self.assertIn('data-story-media-src="https://cdn.example.com/reviews/story.mp4"', content)

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
        self.assertIn("Rapide", content)
        self.assertIn("Capitole highlight", content)
        self.assertIn(marketing_zone.hero_image_url, content)

    def test_service_zone_marketing_overrides_are_used(self):
        MarketingZone.objects.create(
            zone=self.capitole,
            intro="Focus Capitole",
            highlights=["Capitole highlight"],
            hero_image_url="https://cdn.example.com/capitole.jpg",
            meta_description="Meta Capitole",
        )
        service_zone = MarketingServiceZone.objects.create(
            service=self.marketing_service,
            zone=self.capitole,
            intro="Intro personnalisée Capitole",
            short_intro="Short intro Capitole",
            long_description="Description longue Capitole",
            long_title="Titre long Capitole",
            highlights=["Highlight personnalisé"],
            hero_image_url="https://cdn.example.com/tresses-capitole.jpg",
            meta_description="Meta personnalisée",
        )

        url = reverse(
            "interface:service_city_district_page", args=["tresses", "toulouse", "capitole"]
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Highlight personnalisé", content)
        self.assertIn("Short intro Capitole", content)
        self.assertIn("Description longue Capitole", content)
        self.assertIn("Titre long Capitole", content)
        self.assertIn(service_zone.hero_image_url, content)
        self.assertNotIn("Capitole highlight", content)



    def test_home_uses_homepage_order_for_provider_cards(self):
        self.provider_a.homepage_order = 10
        self.provider_a.save()
        self.provider_b.homepage_order = 1
        self.provider_b.save()

        response = self.client.get(reverse("interface:home"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertLess(content.index(self.provider_b.name), content.index(self.provider_a.name))

    def test_home_renders_marketing_city_chips(self):
        response = self.client.get(reverse("interface:home"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Coiffure afro à Toulouse Métropole', content)
        self.assertIn('/villes/balma/', content)
        self.assertIn('Coiffure afro à Tournefeuille', content)
        self.assertNotIn('SEO local', content)

    def test_footer_does_not_render_marketing_city_links(self):
        response = self.client.get(reverse("interface:provider_list"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('Coiffure afro autour de Toulouse', content)
        self.assertNotIn('/villes/colomiers/', content)

    def test_city_page_renders_providers_and_service_links(self):
        response = self.client.get(reverse("interface:city_page", args=["toulouse"]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Coiffure afro à Toulouse', content)
        self.assertNotIn('Prestataires à Toulouse', content)
        self.assertIn('/services/tresses/toulouse/', content)
        self.assertNotIn('Page ville', content)

    def test_at_home_provider_page_filters_providers_by_location_mode(self):
        self.provider_a.location_mode = Provider.LOCATION_MODE_HYBRID
        self.provider_a.save()
        self.provider_b.location_mode = Provider.LOCATION_MODE_SALON_ONLY
        self.provider_b.save()

        response = self.client.get(reverse("interface:at_home_provider_list"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_a.name, content)
        self.assertNotIn(self.provider_b.name, content)

    def test_footer_and_home_link_to_at_home_page(self):
        home = self.client.get(reverse("interface:home"))
        providers = self.client.get(reverse("interface:provider_list"))

        self.assertEqual(home.status_code, 200)
        self.assertEqual(providers.status_code, 200)
        self.assertIn(reverse("interface:at_home_provider_list"), home.content.decode())
        self.assertIn(reverse("interface:at_home_provider_list"), providers.content.decode())
