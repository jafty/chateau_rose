import os
import shutil
import tempfile

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from booking.models import Booking, Provider, ProviderPhoto, ProviderZone, Service, Zone


class _ReleaseAuthStub:
    def __init__(self):
        self.released = []

    def release_auth(self, auth_id):
        self.released.append(auth_id)


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    STRIPE_PUBLIC_KEY="",
    STRIPE_SECRET_KEY="",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class ProviderRequestUploadTests(TestCase):
    def setUp(self):
        self.addCleanup(lambda: shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True))
        self.provider = Provider.objects.create(
            name="Divine",
            salon_zone="Paris 10e",
            salon_address="12 rue des Fleurs, 75010 Paris",
        )
        self.zone = Zone.objects.create(name="Toulouse", slug="toulouse")
        ProviderZone.objects.create(provider=self.provider, zone=self.zone)
        self.service = Service.objects.create(
            provider=self.provider,
            name="Tresses",
            slug="tresses",
            base_price_cents=5000,
            hair_length_adjustments={"medium": 0},
            meche_bonus_cents=500,
        )

    def test_request_uploads_are_saved_and_paths_stored(self):
        url = reverse("interface:provider_detail", args=[self.provider.id])
        current_file = SimpleUploadedFile("current.jpg", b"hair", content_type="image/jpeg")
        insp1 = SimpleUploadedFile("insp1.jpg", b"ref1", content_type="image/jpeg")
        insp2 = SimpleUploadedFile("insp2.jpg", b"ref2", content_type="image/jpeg")

        response = self.client.post(
            url,
            data={
                "service_id": self.service.id,
                "client_name": "Alice",
                "client_email": "test@example.com",
                "location": self.zone.name,
                "client_address": "5 place du Capitole, 31000 Toulouse",
                "desired_date": "2026-01-01",
                "hair_length": "medium",
                "meche": "on",
                "free_text": "Merci",
                "location_preference": "domicile",
                "payment_auth_id": "pi_test_auth",
                "current_hair_picture_file": current_file,
                "inspiration_pictures": [insp1, insp2],
            },
        )

        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get()
        # Current hair picture path stored and file exists
        self.assertTrue(booking.current_hair_picture)
        self.assertTrue(os.path.exists(os.path.join(settings.MEDIA_ROOT, booking.current_hair_picture)))
        # Inspiration pictures stored as a list of paths, files exist
        self.assertEqual(len(booking.inspiration_pictures), 2)
        for path in booking.inspiration_pictures:
            self.assertTrue(os.path.exists(os.path.join(settings.MEDIA_ROOT, path)))
        self.assertTrue(booking.meche)
        self.assertEqual(booking.hair_length, "medium")

    def test_hybrid_provider_allows_salon_choice_without_zone(self):
        url = reverse("interface:provider_detail", args=[self.provider.id])
        current_file = SimpleUploadedFile("current.jpg", b"hair", content_type="image/jpeg")

        response = self.client.post(
            url,
            data={
                "service_id": self.service.id,
                "client_name": "Alice",
                "client_email": "test@example.com",
                "location_preference": "salon",
                "desired_date": "2026-01-01T12:00",
                "hair_length": "medium",
                "payment_auth_id": "pi_test_auth",
                "current_hair_picture_file": current_file,
            },
        )

        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get()
        self.assertEqual(booking.location, "Paris 10e")
        self.assertFalse(booking.meche)

    def test_invalid_form_keeps_existing_payment_auth_id_visible(self):
        url = reverse("interface:provider_detail", args=[self.provider.id])

        response = self.client.post(
            url,
            data={
                "service_id": self.service.id,
                "client_name": "Alice",
                "client_email": "test@example.com",
                "location": self.zone.name,
                "client_address": "",
                "desired_date": "2026-01-01",
                "hair_length": "medium",
                "location_preference": "domicile",
                "payment_auth_id": "pi_auth_saved",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="pi_auth_saved"')
        self.assertEqual(Booking.objects.count(), 0)

    @override_settings(STRIPE_PUBLIC_KEY="pk_test", STRIPE_SECRET_KEY="sk_test")
    def test_salon_configuration_error_releases_existing_payment_auth(self):
        from interface import views

        self.provider.salon_address = ""
        self.provider.save(update_fields=["salon_address"])

        gateway_stub = _ReleaseAuthStub()
        original_gateway = views.payment_gateway
        views.payment_gateway = gateway_stub
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)

        response = self.client.post(
            reverse("interface:provider_detail", args=[self.provider.id]),
            data={
                "service_id": self.service.id,
                "client_name": "Alice",
                "client_email": "test@example.com",
                "location_preference": "salon",
                "desired_date": "2026-01-01T12:00",
                "hair_length": "medium",
                "payment_auth_id": "pi_auth_to_release",
                "current_hair_picture": "existing.jpg",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="pi_auth_to_release"')
        self.assertEqual(gateway_stub.released, ["pi_auth_to_release"])

    def test_provider_detail_renders_service_card_with_service_image(self):
        self.service.image_url = "https://cdn.example.com/services/tresses.jpg"
        self.service.save(update_fields=["image_url"])

        response = self.client.get(reverse("interface:provider_detail", args=[self.provider.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.service.image_url)
        self.assertContains(response, f'alt="{self.service.name} réalisée par {self.provider.name}"')


    def test_provider_detail_uses_custom_seo_h1_when_configured(self):
        self.provider.seo_h1 = "Coiffeuse afro à Paris 10 · tresses naturelles et conseils personnalisés"
        self.provider.save(update_fields=["seo_h1"])

        response = self.client.get(reverse("interface:provider_detail", args=[self.provider.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.provider.seo_h1, html=True)
        self.assertNotContains(response, f'<h1 class="provider-page-title">{self.provider.name}.</h1>', html=False)

    def test_provider_detail_hero_uses_first_four_valid_image_photos(self):
        ProviderPhoto.objects.create(
            provider=self.provider,
            media_kind=ProviderPhoto.MEDIA_VIDEO,
            video_url="https://cdn.example.com/gallery/intro.mp4",
            caption="Intro vidéo",
            order=0,
        )
        for index in range(5):
            ProviderPhoto.objects.create(
                provider=self.provider,
                image_url=f"https://cdn.example.com/gallery/look-{index}.jpg",
                caption=f"Look {index}",
                order=index + 1,
            )

        response = self.client.get(reverse("interface:provider_detail", args=[self.provider.id]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        hero_section = content.split('<div class="provider-hero-collage"', 1)[1].split(
            '<div class="provider-layout stack-card-grid">',
            1,
        )[0]
        self.assertEqual(content.count('class="provider-hero-polaroid"'), 4)
        self.assertNotIn("intro.mp4", hero_section)
        self.assertIn("look-0.jpg", hero_section)
        self.assertIn("look-3.jpg", hero_section)
        self.assertNotIn("look-4.jpg", hero_section)
