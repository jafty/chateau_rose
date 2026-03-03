from unittest.mock import patch

from django.test import TestCase, override_settings

from interface.services.booking_requests import resolve_stored_media_url


class ResolveStoredMediaUrlTests(TestCase):
    def test_resolve_relative_path_uses_storage_url(self):
        with patch("interface.services.booking_requests.default_storage.url", return_value="https://bucket.s3.amazonaws.com/bookings/inspiration/img.jpg?X-Amz-Signature=abc") as url_mock:
            resolved = resolve_stored_media_url("bookings/inspiration/img.jpg")

        self.assertEqual(
            resolved,
            "https://bucket.s3.amazonaws.com/bookings/inspiration/img.jpg?X-Amz-Signature=abc",
        )
        url_mock.assert_called_once_with("bookings/inspiration/img.jpg")


    @override_settings(MEDIA_URL="https://bucket.s3.amazonaws.com/")
    def test_resolve_absolute_media_url_on_same_host_gets_resigned(self):
        with patch("interface.services.booking_requests.default_storage.url", return_value="https://bucket.s3.amazonaws.com/bookings/inspiration/img.jpg?X-Amz-Signature=fresh") as url_mock:
            resolved = resolve_stored_media_url("https://bucket.s3.amazonaws.com/bookings/inspiration/img.jpg")

        self.assertEqual(
            resolved,
            "https://bucket.s3.amazonaws.com/bookings/inspiration/img.jpg?X-Amz-Signature=fresh",
        )
        url_mock.assert_called_once_with("bookings/inspiration/img.jpg")

    def test_resolve_absolute_url_kept(self):
        absolute = "https://example.com/path.jpg"
        self.assertEqual(resolve_stored_media_url(absolute), absolute)

    def test_resolve_root_relative_kept(self):
        root_relative = "/media/bookings/inspiration/img.jpg"
        self.assertEqual(resolve_stored_media_url(root_relative), root_relative)
