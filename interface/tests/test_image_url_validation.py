from django.core.exceptions import ValidationError
from django.test import TestCase

from interface.models import MarketingService


class ImageUrlValidationTests(TestCase):
    def test_service_main_image_url_accepts_root_relative(self):
        service = MarketingService(name="Test", slug="test", main_image_url="/static/foo.jpg")
        service.full_clean()  # should not raise

    def test_service_main_image_url_accepts_relative_static_path(self):
        service = MarketingService(name="Test", slug="test", main_image_url="static/foo.jpg")
        service.full_clean()  # should not raise

    def test_rejects_invalid_url_formats(self):
        service = MarketingService(name="Test", slug="test", main_image_url="not a url")
        with self.assertRaises(ValidationError):
            service.full_clean()
