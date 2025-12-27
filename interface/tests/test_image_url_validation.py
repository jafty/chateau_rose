from django.core.exceptions import ValidationError
from django.test import TestCase

from interface.models import MarketingCity, MarketingService, MarketingServiceCity


class ImageUrlValidationTests(TestCase):
    def test_service_main_image_url_accepts_root_relative(self):
        service = MarketingService(name="Test", slug="test", main_image_url="/static/foo.jpg")
        service.full_clean()  # should not raise

    def test_city_main_image_url_accepts_root_relative(self):
        city = MarketingCity(name="Toulouse", slug="toulouse", main_image_url="/static/city.jpg")
        city.full_clean()

    def test_override_main_image_url_accepts_root_relative(self):
        service = MarketingService.objects.create(name="Test", slug="test")
        city = MarketingCity.objects.create(name="Toulouse", slug="toulouse")
        override = MarketingServiceCity(
            service=service, city=city, main_image_url="/static/override.jpg"
        )
        override.full_clean()

    def test_rejects_invalid_url_formats(self):
        service = MarketingService(name="Test", slug="test", main_image_url="not a url")
        with self.assertRaises(ValidationError):
            service.full_clean()
