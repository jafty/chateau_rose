import os
import shutil
import tempfile

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from booking.models import Booking, Provider, ProviderZone, Service, Zone
from chateaurose.infrastructure.provider_catalog import SALON_LOCATION_LABEL


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProviderRequestUploadTests(TestCase):
    def setUp(self):
        self.addCleanup(lambda: shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True))
        self.provider = Provider.objects.create(name="Divine")
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
                "client_phone": "0600000000",
                "location": self.zone.name,
                "desired_date": "2026-01-01",
                "hair_length": "medium",
                "meche": "on",
                "free_text": "Merci",
                "location_preference": "domicile",
                "current_hair_picture_file": current_file,
                "inspiration_pictures": [insp1, insp2],
            },
        )

        self.assertEqual(response.status_code, 200)
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
                "client_phone": "0600000000",
                "location_preference": "salon",
                "desired_date": "2026-01-01T12:00",
                "hair_length": "medium",
                "current_hair_picture_file": current_file,
            },
        )

        self.assertEqual(response.status_code, 200)
        booking = Booking.objects.get()
        self.assertEqual(booking.location, SALON_LOCATION_LABEL)
        self.assertFalse(booking.meche)
