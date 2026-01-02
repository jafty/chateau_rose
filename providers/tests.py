from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking, Provider, Service


class ProviderDashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="provider",
            password="safepass123",
            email="provider@example.com",
        )
        self.provider = Provider.objects.create(
            name="Coiffeuse Pro",
            description="",
            contact_phone="+33102030405",
            contact_email="provider@example.com",
            user=self.user,
        )
        self.service = Service.objects.create(
            provider=self.provider,
            name="Tresses",
            slug="tresses",
            base_price_cents=5000,
            hair_length_adjustments={"long": 1500},
        )
        self.client = Client()
        self.client.login(username="provider", password="safepass123")

    def _create_booking(self, status="SUBMITTED"):
        return Booking.objects.create(
            booking_id="BK-1234ABCD",
            provider=self.provider,
            service=self.service,
            client_name="Sarah",
            client_phone="+33600000000",
            location="Paris",
            desired_date="2026-01-10T17:00:00Z",
            hair_length="long",
            meche=True,
            current_hair_picture="/media/hair.jpg",
            inspiration_pictures=[],
            free_text="",
            estimated_price_cents=6500,
            payment_auth_id="auth_1",
            status=status,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

    def test_dashboard_lists_clickable_bookings(self):
        booking = self._create_booking()

        response = self.client.get(reverse("providers:providers_index"))

        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])
        self.assertContains(response, detail_url)
        self.assertContains(response, booking.booking_id)

    def test_provider_can_propose_update_from_detail(self):
        booking = self._create_booking()
        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])

        response = self.client.post(
            detail_url,
            {
                "action": "propose",
                "proposed_price_cents": "7200",
                "proposed_date": "2026-02-01T10:00",
            },
            follow=True,
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(booking.status, "PENDING_CLIENT_VALIDATION")
        self.assertEqual(booking.proposed_price_cents, 7200)
        self.assertEqual(booking.proposed_date, "2026-02-01T10:00")

    def test_provider_can_confirm_booking_from_detail(self):
        booking = self._create_booking()
        detail_url = reverse("providers:booking_detail", args=[booking.booking_id])

        response = self.client.post(detail_url, {"action": "confirm"}, follow=True)

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(booking.status, "CONFIRMED")


class ProviderSignupTests(TestCase):
    def test_provider_can_register_and_login(self):
        client = Client()
        response = client.post(
            reverse("providers:signup"),
            {
                "username": "newprovider",
                "password1": "SafePassw0rd!",
                "password2": "SafePassw0rd!",
                "email": "new@pro.fr",
                "name": "Nouvelle Pro",
                "contact_email": "new@pro.fr",
                "contact_phone": "+33102030405",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        created_user = get_user_model().objects.get(username="newprovider")
        provider = Provider.objects.get(user=created_user)

        self.assertEqual(provider.name, "Nouvelle Pro")
        self.assertEqual(provider.contact_email, "new@pro.fr")
        self.assertTrue(response.wsgi_request.user.is_authenticated)
