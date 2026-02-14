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

    def test_card_main_image_prefers_first_gallery_photo(self):
        provider = Provider.objects.create(
            name="Main Visual",
            profile_image_url="https://cdn.example.com/avatar.jpg",
        )
        ProviderPhoto.objects.create(
            provider=provider,
            image_url="https://cdn.example.com/work.jpg",
            order=0,
        )

        provider.refresh_from_db()
        self.assertEqual(provider.card_main_image, "https://cdn.example.com/work.jpg")
        self.assertEqual(provider.card_identity_image, "https://cdn.example.com/avatar.jpg")

    def test_card_images_fallback_to_profile_when_gallery_empty(self):
        provider = Provider.objects.create(
            name="Fallback",
            profile_image_url="https://cdn.example.com/profile.jpg",
        )

        self.assertEqual(provider.card_main_image, "https://cdn.example.com/profile.jpg")
        self.assertEqual(provider.card_identity_image, "https://cdn.example.com/profile.jpg")
