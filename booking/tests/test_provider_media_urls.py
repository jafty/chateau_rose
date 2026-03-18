from django.core.exceptions import ValidationError
from django.test import TestCase

from booking.models import Provider, ProviderPhoto, Service


class ProviderMediaUrlValidationTests(TestCase):
    def test_profile_image_url_accepts_relative_static(self):
        provider = Provider(name="Test Provider", profile_image_url="static/providers/test.jpg")
        provider.full_clean()

    def test_provider_photo_url_accepts_relative_static(self):
        provider = Provider.objects.create(name="Photo Owner")
        photo = ProviderPhoto(provider=provider, image_url="images/gallery/pic.jpg")
        photo.full_clean()

    def test_invalid_profile_image_url_rejected(self):
        provider = Provider(name="Invalid", profile_image_url="javascript:alert('xss')")
        with self.assertRaises(ValidationError):
            provider.full_clean()

    def test_service_image_url_accepts_relative_static(self):
        provider = Provider.objects.create(name="Service Owner")
        service = Service(provider=provider, name="Tresses", image_url="static/services/tresses.jpg", base_price_cents=4500)
        service.full_clean()


class ProviderMediaResolutionTests(TestCase):
    def test_provider_photo_resolved_url_uses_video_when_media_kind_is_video(self):
        provider = Provider.objects.create(name="Video Owner")
        photo = ProviderPhoto.objects.create(
            provider=provider,
            media_kind=ProviderPhoto.MEDIA_VIDEO,
            video_url="https://cdn.example.com/gallery/video.mp4",
        )

        self.assertTrue(photo.is_video)
        self.assertEqual(photo.resolved_url, "https://cdn.example.com/gallery/video.mp4")

    def test_service_resolved_image_uses_its_own_image_url_before_provider_cover(self):
        provider = Provider.objects.create(name="Image Owner", profile_image_url="https://cdn.example.com/provider.jpg")
        service = Service.objects.create(
            provider=provider,
            name="Vanilles",
            base_price_cents=3000,
            image_url="https://cdn.example.com/services/vanilles.jpg",
        )

        self.assertEqual(service.resolved_image, "https://cdn.example.com/services/vanilles.jpg")
