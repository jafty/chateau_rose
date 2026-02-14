from django.core.exceptions import ValidationError
from django.test import TestCase

from booking.models import Provider, ProviderPhoto


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
