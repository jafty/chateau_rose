from datetime import timedelta
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.models import Provider, Service
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
        self.provider = Provider.objects.create(name="Diva", deposit_percentage=25)
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
            hair_length="long",
            location_preference="salon",
            fixed_price_cents=12000,
        )

    def test_quick_checkout_page_renders_summary_and_payment_step(self):
        response = self.client.get(reverse("interface:quick_checkout_page", args=[self.checkout.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Récapitulatif de ton rendez-vous")
        self.assertContains(response, 'data-quick-checkout-id="{}"'.format(self.checkout.id))

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
                "general_adjustment": "",
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
            data={
                "provider_id": self.provider.id,
                "quick_checkout_id": self.checkout.id,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(stub.calls[0]["amount_cents"], 3000)

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_payment_intent_rejects_quick_checkout_id_with_mismatched_service(self):
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

        self.assertEqual(response.status_code, 400)
