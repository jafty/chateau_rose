from django.test import TestCase
from django.urls import reverse

from booking.models import Provider


class RemovedBookingDraftEndpointTests(TestCase):
    def test_booking_draft_endpoint_is_not_registered(self):
        Provider.objects.create(name="Diva")

        with self.assertRaises(Exception):
            reverse("interface:provider_booking_draft")
