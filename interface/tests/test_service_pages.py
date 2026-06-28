from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from booking.models import Provider, ProviderMarketingService, ProviderZone, Zone
from interface.models import (
    ClientReview,
    Interaction,
    MarketingService,
    MarketingSubServiceImage,
    MarketingServiceZone,
    MarketingSubService,
    MarketingZone,
    ServiceRequest,
)


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
        self.provider_c = Provider.objects.create(name="Prestataire C")

        ProviderMarketingService.objects.create(
            provider=self.provider_a, service=self.marketing_service
        )

        ProviderZone.objects.create(provider=self.provider_a, zone=self.toulouse)
        ProviderZone.objects.create(provider=self.provider_a, zone=self.capitole)
        ProviderZone.objects.create(provider=self.provider_b, zone=self.colomiers)
        ProviderZone.objects.create(provider=self.provider_c, zone=self.toulouse)

        MarketingZone.objects.create(zone=self.toulouse)
        self.sub_service = MarketingSubService.objects.create(
            service=self.marketing_service,
            name="Knotless braids",
            slug="knotless-braids",
            generic_base_price_cents=6500,
        )
        self.sub_service.providers.add(self.provider_a)

    def test_service_page_filters_providers_by_service(self):
        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_a.name, content)
        self.assertNotIn(self.provider_b.name, content)

    def test_locks_service_page_renders_with_provider_cards(self):
        locks = MarketingService.objects.create(
            name="Locks",
            slug="locks",
            intro="Intro locks",
            short_intro="Intro courte locks",
            long_description="Description longue locks",
            long_title="Titre long locks",
        )
        locks_provider = Provider.objects.create(name="Locks Studio")
        ProviderMarketingService.objects.create(provider=locks_provider, service=locks)
        ProviderZone.objects.create(provider=locks_provider, zone=self.toulouse)

        response = self.client.get(reverse("interface:service_page", args=["locks"]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Locks", content)
        self.assertIn(locks_provider.name, content)

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

    def test_service_page_renders_sub_service_cards_and_support_cta(self):
        response = self.client.get(reverse("interface:service_page", args=["tresses"]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Knotless braids", content)
        self.assertIn(
            '<a class="provider-service-card provider-service-card--link" '
            'href="/services/tresses/sous-services/knotless-braids/"',
            content,
        )
        self.assertIn(
            '<span class="btn btn-accent provider-service-card__button" aria-hidden="true">Réserver rapidement</span>',
            content,
        )
        self.assertNotIn("Une question ? Écris-nous", content)
        self.assertIn('href="mailto:japhet.situmonana@gmail.com"', content)

    def test_sub_service_page_filters_providers_without_zone_filter(self):
        self.sub_service.providers.add(self.provider_c)

        response = self.client.get(
            reverse("interface:sub_service_page", args=["tresses", "knotless-braids"])
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_a.name, content)
        self.assertIn(self.provider_c.name, content)
        self.assertNotIn(self.provider_b.name, content)
        self.assertNotIn("Affiner par zone", content)
        self.assertIn("Knotless braids : l&#x27;essentiel", content)
        self.assertNotIn("Description longue tresses", content)


    def test_sub_service_page_includes_card_image_in_gallery_by_default(self):
        self.sub_service.image_url = "https://static.example.com/knotless-card.jpg"
        self.sub_service.save()

        response = self.client.get(
            reverse("interface:sub_service_page", args=["tresses", "knotless-braids"])
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Inspirations & résultats", content)
        self.assertIn("service-header-with-collage", content)
        self.assertIn("https://static.example.com/knotless-card.jpg", content)
        self.assertIn('data-gallery-caption="Knotless braids"', content)

    def test_sub_service_gallery_does_not_duplicate_card_image(self):
        self.sub_service.image_url = "https://static.example.com/knotless-card.jpg"
        self.sub_service.save()
        MarketingSubServiceImage.objects.create(
            sub_service=self.sub_service,
            image_url="https://static.example.com/knotless-card.jpg",
            caption="Duplicate card image",
        )

        response = self.client.get(
            reverse("interface:sub_service_page", args=["tresses", "knotless-braids"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://static.example.com/knotless-card.jpg", count=3)
        self.assertNotIn("Duplicate card image", response.content.decode())

    def test_sub_service_page_renders_dedicated_gallery_images(self):
        MarketingSubServiceImage.objects.create(
            sub_service=self.sub_service,
            image_url="https://static.example.com/knotless-result.jpg",
            caption="Résultat knotless",
        )

        response = self.client.get(
            reverse("interface:sub_service_page", args=["tresses", "knotless-braids"])
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Inspirations & résultats", content)
        self.assertIn("https://static.example.com/knotless-result.jpg", content)
        self.assertIn("Résultat knotless", content)

    def test_sub_service_page_renders_first_four_gallery_images_in_hero_collage(self):
        for index in range(5):
            MarketingSubServiceImage.objects.create(
                sub_service=self.sub_service,
                image_url=f"https://static.example.com/knotless-hero-{index}.jpg",
                caption=f"Résultat knotless {index}",
                order=index,
            )

        response = self.client.get(
            reverse("interface:sub_service_page", args=["tresses", "knotless-braids"])
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("service-header-with-collage", content)
        self.assertIn("service-hero-collage", content)
        self.assertIn("Aperçu des inspirations Knotless braids", content)
        self.assertContains(response, '<figure class="service-hero-polaroid">', count=4)
        self.assertIn("https://static.example.com/knotless-hero-0.jpg", content)
        self.assertIn("https://static.example.com/knotless-hero-3.jpg", content)

    def test_service_at_home_page_filters_only_mobile_providers(self):
        self.provider_a.location_mode = Provider.LOCATION_MODE_HYBRID
        self.provider_a.save()
        self.provider_b.location_mode = Provider.LOCATION_MODE_SALON_ONLY
        self.provider_b.save()
        self.provider_c.location_mode = Provider.LOCATION_MODE_CLIENT_HOME_ONLY
        self.provider_c.save()
        ProviderMarketingService.objects.create(
            provider=self.provider_c, service=self.marketing_service
        )

        response = self.client.get(reverse("interface:service_at_home_page", args=["tresses"]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_a.name, content)
        self.assertIn(self.provider_c.name, content)
        self.assertNotIn(self.provider_b.name, content)
        self.assertIn("Tresses / Braids à domicile", content)

    def test_sub_service_at_home_page_filters_only_mobile_providers(self):
        self.provider_a.location_mode = Provider.LOCATION_MODE_SALON_ONLY
        self.provider_a.save()
        self.provider_c.location_mode = Provider.LOCATION_MODE_CLIENT_HOME_ONLY
        self.provider_c.save()
        self.sub_service.providers.add(self.provider_c)

        response = self.client.get(
            reverse("interface:sub_service_at_home_page", args=["tresses", "knotless-braids"])
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_c.name, content)
        self.assertNotIn(self.provider_a.name, content)
        self.assertIn("Knotless braids à domicile", content)

    def test_sub_service_at_home_page_reuses_dedicated_gallery_images(self):
        MarketingSubServiceImage.objects.create(
            sub_service=self.sub_service,
            image_url="https://static.example.com/knotless-at-home.jpg",
            caption="Résultat knotless à domicile",
        )

        response = self.client.get(
            reverse("interface:sub_service_at_home_page", args=["tresses", "knotless-braids"])
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Inspirations & résultats", content)
        self.assertIn("https://static.example.com/knotless-at-home.jpg", content)
        self.assertIn("Résultat knotless à domicile", content)

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
                "contact": "0612345678",
                "availabilities": ["weekday_morning", "weekend_afternoon"],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("interface:thank_you_quick_request"))
        self.assertEqual(ServiceRequest.objects.count(), 1)
        request_record = ServiceRequest.objects.first()
        self.assertEqual(request_record.marketing_service, self.marketing_service)
        self.assertIsNone(request_record.zone)
        self.assertEqual(
            request_record.location_preference, ServiceRequest.LOCATION_PREFERENCE_CLIENT_HOME
        )
        self.assertIsNone(request_record.desired_date)
        self.assertEqual(request_record.client_email, "")
        self.assertEqual(request_record.client_phone, "0612345678")
        self.assertEqual(request_record.availabilities, ["weekday_morning", "weekend_afternoon"])


    def test_service_page_creates_quick_request_interaction_and_sets_reply_to(self):
        url = reverse("interface:service_page", args=["tresses"])

        with patch("interface.views.notifier.notify") as notify_mock:
            response = self.client.post(
                url,
                {
                    "request_service": "1",
                    "contact": "0612345678",
                    "availabilities": ["weekday_evening"],
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("interface:thank_you_quick_request"))
        notify_mock.assert_called_once()
        self.assertEqual(
            notify_mock.call_args.kwargs["reply_to"],
            "japhet.situmonana@gmail.com",
        )

        interaction = Interaction.objects.get(kind=Interaction.KIND_QUICK_REQUEST)
        self.assertEqual(interaction.contact_phone, "0612345678")
        self.assertEqual(interaction.contact_email, "")
        self.assertEqual(interaction.next_action, "Contacter la cliente / le client rapidement")


    def test_home_quick_request_validation_error_keeps_user_on_form_with_feedback(self):
        response = self.client.post(
            reverse("interface:home"),
            {
                "request_service": "1",
                "contact": "",
                "availabilities": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "On n'a pas pu envoyer ta demande.")
        self.assertContains(response, "Ce champ est obligatoire.")
        self.assertEqual(ServiceRequest.objects.count(), 0)

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
        self.assertNotIn("request-wizard-form", content)


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

    def test_salon_only_location_text_is_rendered(self):
        self.provider_a.location_mode = Provider.LOCATION_MODE_SALON_ONLY
        self.provider_a.save()

        url = reverse("interface:service_page", args=["tresses"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Reçoit uniquement", content)
        self.assertNotIn("Salon</span>", content)

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
        self.assertNotIn("Capitole highlight", content)




    def test_hidden_provider_is_excluded_from_public_provider_lists(self):
        self.provider_b.is_visible_on_website = False
        self.provider_b.save()

        response = self.client.get(reverse("interface:provider_list"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_a.name, content)
        self.assertNotIn(self.provider_b.name, content)

    def test_hidden_provider_detail_is_not_public(self):
        self.provider_b.is_visible_on_website = False
        self.provider_b.save()

        response = self.client.get(reverse("interface:provider_detail", args=[self.provider_b.id]))

        self.assertEqual(response.status_code, 404)

    def test_hidden_provider_is_excluded_from_service_pages(self):
        ProviderMarketingService.objects.create(
            provider=self.provider_b, service=self.marketing_service
        )
        self.provider_b.is_visible_on_website = False
        self.provider_b.save()

        response = self.client.get(reverse("interface:service_page", args=["tresses"]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.provider_a.name, content)
        self.assertNotIn(self.provider_b.name, content)

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
        self.assertIn('Coiffure tous types de cheveux à Toulouse et alentours', content)
        self.assertIn('/villes/balma/', content)
        self.assertIn('Coiffure à Tournefeuille', content)
        self.assertNotIn('SEO local', content)

    def test_home_hides_marketing_services_marked_hidden(self):
        hidden_service = MarketingService.objects.create(
            name="Service caché",
            slug="service-cache",
            is_visible_on_homepage=False,
        )

        response = self.client.get(reverse("interface:home"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.marketing_service.name, content)
        self.assertNotIn(hidden_service.name, content)

    def test_home_orders_marketing_services_with_homepage_order(self):
        slow_service = MarketingService.objects.create(
            name="Service lent",
            slug="service-lent",
            homepage_order=10,
        )
        fast_service = MarketingService.objects.create(
            name="Service rapide",
            slug="service-rapide",
            homepage_order=1,
        )

        response = self.client.get(reverse("interface:home"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertLess(content.index(fast_service.name), content.index(slow_service.name))

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

    def test_service_page_shows_quick_booking_primary_cta_and_provider_choice_secondary_cta(self):
        response = self.client.get(reverse("interface:service_page", args=["tresses"]))

        self.assertContains(response, "Dès")
        self.assertContains(response, "65€")
        self.assertContains(response, "Réserver rapidement")
        self.assertContains(response, 'href="#service-subservices"')
        self.assertContains(response, 'id="service-subservices"')
        self.assertContains(response, "Choisir un profil")

    def test_sub_service_page_quick_booking_cta_targets_request_form(self):
        response = self.client.get(reverse("interface:sub_service_page", args=["tresses", "knotless-braids"]))

        self.assertContains(response, 'href="#service-request"')

    @override_settings(GENERIC_BOOKING_PLATFORM_FEE_CENTS=0)
    def test_generic_booking_form_creates_waiting_booking_without_provider(self):
        response = self.client.post(
            reverse("interface:sub_service_page", args=["tresses", "knotless-braids"]),
            {
                "request_service": "1",
                "client_name": "Awa Diallo",
                "client_email": "awa@example.com",
                "client_phone": "0600000000",
                "desired_date": "2026-02-01T10:00",
                "location_preference": "salon",
                "hair_length": "standard",
                "requested_options": "extra-long",
            },
        )

        self.assertRedirects(response, reverse("interface:thank_you_quick_request"))
        from booking.models import Booking

        booking = Booking.objects.get(client_email="awa@example.com")
        self.assertIsNone(booking.provider)
        self.assertEqual(booking.status, Booking.STATUS_WAITING_PROVIDER_ASSIGNMENT)
        self.assertEqual(booking.booking_kind, Booking.KIND_GENERIC)
        self.assertEqual(booking.requested_marketing_service, self.marketing_service)
        self.assertEqual(booking.requested_marketing_sub_service, self.sub_service)
        self.assertEqual(booking.payment_status, Booking.PAYMENT_STATUS_WAIVED)

    def test_enabled_generic_booking_redirects_to_recap_then_creates_booking(self):
        self.sub_service.generic_booking_enabled = True
        self.sub_service.generic_base_price_cents = 10000
        self.sub_service.generic_hair_length_adjustments = {"standard": 0}
        self.sub_service.generic_general_adjustments = {"extra-long": 2500}
        self.sub_service.generic_service_fee_percentage = 0
        self.sub_service.save()

        response = self.client.post(
            reverse("interface:sub_service_page", args=["tresses", "knotless-braids"]),
            {
                "request_service": "1",
                "client_name": "Awa Diallo",
                "client_email": "awa-recap@example.com",
                "client_phone": "0600000000",
                "desired_date": "2026-02-01T10:00",
                "location_preference": "salon",
                "hair_length": "standard",
                "requested_options": "extra-long",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("interface:generic_booking_recap", args=["00000000-0000-0000-0000-000000000000"]).rsplit("/", 2)[0], response["Location"])
        recap_response = self.client.post(response["Location"])
        self.assertRedirects(recap_response, reverse("interface:thank_you_quick_request"))

        from booking.models import Booking

        booking = Booking.objects.get(client_email="awa-recap@example.com")
        self.assertIsNone(booking.provider)
        self.assertEqual(booking.status, Booking.STATUS_WAITING_PROVIDER_ASSIGNMENT)
        self.assertEqual(booking.provider_price_estimate_cents, 12500)
        self.assertEqual(booking.amount_due_now_cents, 0)
        self.assertEqual(booking.payment_status, Booking.PAYMENT_STATUS_WAIVED)
