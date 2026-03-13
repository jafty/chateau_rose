from django.contrib.admin.sites import AdminSite
from django.test import TestCase, override_settings

from booking.admin import BookingAdmin
from booking.models import Booking, Provider, Service


class BookingAdminTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Diva")
        self.service = Service.objects.create(
            provider=self.provider,
            name="Tresses",
            slug="tresses",
            base_price_cents=5000,
        )
        self.booking = Booking.objects.create(
            booking_id="BK-TEST01",
            provider=self.provider,
            service=self.service,
            client_name="Alice",
            client_email="alice@example.com",
            location="Toulouse",
            location_preference="domicile",
            client_address="5 place du Capitole, Toulouse",
            desired_date="2026-01-01T10:00:00+00:00",
            hair_length="medium",
            general_adjustments=[],
            meche=False,
            current_hair_picture="bookings/current/current.jpg",
            inspiration_pictures=["bookings/inspiration/a.jpg", "bookings/inspiration/b.jpg"],
            free_text="",
            estimated_price_cents=8000,
            payment_auth_id="pi_123",
            status="SUBMITTED",
            created_at="2026-01-01T09:00:00+00:00",
        )
        self.model_admin = BookingAdmin(Booking, AdminSite())

    def test_inspiration_pictures_count_matches_payload(self):
        self.assertEqual(self.model_admin.inspiration_pictures_count(self.booking), 2)

    @override_settings(MEDIA_URL="/media/")
    def test_current_hair_picture_preview_displays_media_url(self):
        html = str(self.model_admin.current_hair_picture_preview(self.booking))

        self.assertIn('/media/bookings/current/current.jpg', html)
        self.assertIn("<img", html)

    @override_settings(MEDIA_URL="/media/")
    def test_inspiration_pictures_preview_displays_all_images(self):
        html = str(self.model_admin.inspiration_pictures_preview(self.booking))

        self.assertIn('/media/bookings/inspiration/a.jpg', html)
        self.assertIn('/media/bookings/inspiration/b.jpg', html)
        self.assertIn("Ouvrir l'image 1", html)
        self.assertIn("Ouvrir l'image 2", html)
