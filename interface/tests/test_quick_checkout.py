from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking, Provider, Service
from interface.models import QuickCheckoutPage


class _PaymentStub:
    def __init__(self):
        self.calls = []

    def create_payment_intent(self, amount_cents, currency, reference):
        self.calls.append({"amount_cents": amount_cents, "currency": currency, "reference": reference})
        return {"id": "pi_auth_1", "client_secret": "secret_123"}


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class QuickCheckoutViewTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Diva", deposit_percentage=25, salon_zone="Paris", salon_address="12 rue des Fleurs, 75010 Paris")
        self.service = Service.objects.create(
            provider=self.provider,
            name="Tresses",
            slug="tresses",
            base_price_cents=5000,
            hair_length_adjustments={"long": 2000},
        )
        self.checkout = QuickCheckoutPage.objects.create(
            provider=self.provider,
            service=self.service,
            client_name="Léa",
            client_email="lea@example.com",
            desired_date=timezone.now() + timedelta(days=3),
            location_preference="salon",
            final_price_cents=12000,
            reservation_fee_cents=3000,
        )

    def test_quick_checkout_page_renders_summary_and_payment_step(self):
        response = self.client.get(reverse("interface:quick_checkout_page", args=[self.checkout.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Récapitulatif de ton rendez-vous")
        self.assertContains(response, "120,00 €")
        self.assertContains(response, "30,00 €")
        self.assertNotContains(response, "centimes")
        self.assertNotContains(response, 'class="step-progress"')
        self.assertNotContains(response, "Estimation totale")
        self.assertContains(response, "Valider")
        self.assertContains(response, f'data-quick-checkout-id="{self.checkout.id}"')





    def test_quick_checkout_page_hides_address_field_for_salon(self):
        response = self.client.get(reverse("interface:quick_checkout_page", args=[self.checkout.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Informations de lieu" hidden')

    def test_quick_checkout_page_shows_address_field_for_domicile(self):
        self.checkout.location_preference = "domicile"
        self.checkout.save(update_fields=["location_preference", "updated_at"])

        response = self.client.get(reverse("interface:quick_checkout_page", args=[self.checkout.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ton adresse complète")
        self.assertContains(response, 'name="client_address"')

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_quick_checkout_submit_requires_address_for_domicile(self):
        self.checkout.location_preference = "domicile"
        self.checkout.save(update_fields=["location_preference", "updated_at"])

        response = self.client.post(
            reverse("interface:quick_checkout_page", args=[self.checkout.id]),
            data={"payment_auth_id": "pi_auth_1", "client_address": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "adresse complète pour le rendez-vous à domicile")

    def test_quick_checkout_summary_shows_fee_and_hides_location_label(self):
        response = self.client.get(reverse("interface:quick_checkout_page", args=[self.checkout.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Frais de réservation")
        self.assertNotContains(response, "Chez la/le prestataire ou en salon")
        self.assertNotContains(response, "Paris")

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_quick_checkout_submit_redirects_to_confirmation_and_marks_booking_confirmed(self):
        response = self.client.post(
            reverse("interface:quick_checkout_page", args=[self.checkout.id]),
            data={"payment_auth_id": "pi_auth_1"},
        )

        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get()
        self.assertRedirects(
            response,
            reverse("interface:quick_checkout_confirmation", args=[booking.booking_id]),
        )
        self.assertEqual(booking.status, "CONFIRMED")
        self.checkout.refresh_from_db()
        self.assertFalse(self.checkout.is_active)
        self.assertIsNotNone(self.checkout.completed_at)

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_quick_checkout_confirmation_page_renders_booking_summary(self):
        self.client.post(
            reverse("interface:quick_checkout_page", args=[self.checkout.id]),
            data={"payment_auth_id": "pi_auth_1"},
        )
        booking = Booking.objects.get()

        response = self.client.get(
            reverse("interface:quick_checkout_confirmation", args=[booking.booking_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rendez-vous confirmé")
        self.assertContains(response, booking.booking_id)
        self.assertContains(response, "Contacter le profil partenaire")
        self.assertContains(response, "12 rue des Fleurs, 75010 Paris")

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_payment_intent_uses_fixed_quick_checkout_price(self):
        from interface import views

        stub = _PaymentStub()
        original_gateway = views.payment_gateway
        views.payment_gateway = stub
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)

        response = self.client.post(
            reverse("interface:provider_payment_intent"),
            data={
                "provider_id": self.provider.id,
                "service_id": self.service.id,
                "hair_length": "long",
                "general_adjustments": [],
                "meche": False,
                "location_preference": "salon",
                "quick_checkout_id": self.checkout.id,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(stub.calls[0]["amount_cents"], 3000)

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_payment_intent_accepts_quick_checkout_id_without_client_fields(self):
        from interface import views

        stub = _PaymentStub()
        original_gateway = views.payment_gateway
        views.payment_gateway = stub
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)

        response = self.client.post(
            reverse("interface:provider_payment_intent"),
            data={"quick_checkout_id": self.checkout.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(stub.calls[0]["amount_cents"], 3000)

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_payment_intent_ignores_unrelated_service_fields_for_quick_checkout(self):
        from interface import views

        other_service = Service.objects.create(
            provider=self.provider,
            name="Twists",
            slug="twists",
            base_price_cents=4000,
        )

        stub = _PaymentStub()
        original_gateway = views.payment_gateway
        views.payment_gateway = stub
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)

        response = self.client.post(
            reverse("interface:provider_payment_intent"),
            data={
                "provider_id": self.provider.id,
                "service_id": other_service.id,
                "quick_checkout_id": self.checkout.id,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(stub.calls[0]["amount_cents"], 3000)
