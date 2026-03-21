from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking, Provider, Service
from interface.models import Interaction, QuickCheckoutPage


class _PaymentStub:
    def __init__(self):
        self.calls = []

    def create_payment_intent(self, amount_cents, currency, reference):
        self.calls.append({"amount_cents": amount_cents, "currency": currency, "reference": reference})
        return {"id": "pi_auth_1", "client_secret": "secret_123"}






class _CatalogBlockedSlotStub:
    def __init__(self, reason=None):
        self.reason = reason

    def get_service(self, provider_id, service_id):
        return {
            "id": str(service_id),
            "provider_id": str(provider_id),
            "name": "Tresses",
            "base_price_cents": 5000,
            "hair_length_adjustments": {"long": 2000},
            "general_adjustments": {},
            "meche_bonus_cents": 0,
            "at_home_bonus_cents": 0,
            "deposit_percentage": 25,
            "deposit_cents": None,
        }

    def get_blocked_slot_details(self, provider_id, desired_date):
        return {"reason": self.reason}


class _PaymentReturnStub:
    def __init__(self, status):
        self.status = status

    def retrieve_payment_intent(self, intent_id):
        return {"id": intent_id, "status": self.status}


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

    def test_quick_checkout_page_stays_accessible_when_provider_is_hidden_on_website(self):
        self.provider.is_visible_on_website = False
        self.provider.save(update_fields=["is_visible_on_website"])

        response = self.client.get(reverse("interface:quick_checkout_page", args=[self.checkout.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Finaliser ta demande")

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

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_quick_checkout_page_hides_payment_form_when_reservation_fee_is_zero(self):
        self.checkout.reservation_fee_cents = 0
        self.checkout.save(update_fields=["reservation_fee_cents", "updated_at"])

        response = self.client.get(reverse("interface:quick_checkout_page", args=[self.checkout.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Réservation offerte")
        self.assertNotContains(response, "Saisir la carte pour valider l'empreinte bancaire")

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_quick_checkout_submit_works_without_payment_auth_when_reservation_fee_is_zero(self):
        self.checkout.reservation_fee_cents = 0
        self.checkout.save(update_fields=["reservation_fee_cents", "updated_at"])

        response = self.client.post(
            reverse("interface:quick_checkout_page", args=[self.checkout.id]),
            data={},
        )

        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get()
        self.assertTrue(booking.payment_auth_id.startswith("free_quick_checkout_"))





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

    def test_quick_checkout_summary_displays_note_when_present(self):
        self.checkout.free_text = "Merci de prévoir un créneau calme"
        self.checkout.save(update_fields=["free_text", "updated_at"])

        response = self.client.get(reverse("interface:quick_checkout_page", args=[self.checkout.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Note")
        self.assertContains(response, "Merci de prévoir un créneau calme")

    def test_quick_checkout_summary_shows_fee_and_hides_location_label(self):
        response = self.client.get(reverse("interface:quick_checkout_page", args=[self.checkout.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Frais de réservation")
        self.assertNotContains(response, "Chez la prestataire")
        self.assertNotContains(response, "Paris")


    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_quick_checkout_submit_redirects_to_thank_you_page_and_keeps_booking_pending(self):
        response = self.client.post(
            reverse("interface:quick_checkout_page", args=[self.checkout.id]),
            data={"payment_auth_id": "pi_auth_1"},
        )

        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get()
        self.assertRedirects(
            response,
            reverse("interface:thank_you_provider_booking") + f"?provider={self.provider.name}",
            fetch_redirect_response=False,
        )
        self.assertEqual(booking.status, "SUBMITTED")
        self.checkout.refresh_from_db()
        self.assertFalse(self.checkout.is_active)
        self.assertIsNotNone(self.checkout.completed_at)

        interaction = Interaction.objects.get(kind=Interaction.KIND_PROVIDER_APPOINTMENT_REQUEST)
        self.assertEqual(interaction.contact_email, "lea@example.com")
        self.assertEqual(interaction.metadata.get("booking_id"), booking.booking_id)

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_client_confirmation_page_renders_pending_summary_after_quick_checkout(self):
        self.client.post(
            reverse("interface:quick_checkout_page", args=[self.checkout.id]),
            data={"payment_auth_id": "pi_auth_1"},
        )
        booking = Booking.objects.get()

        response = self.client.get(
            reverse("interface:client_confirmation", args=[booking.booking_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ta demande est en cours")
        self.assertContains(response, booking.booking_id)
        self.assertContains(response, "Contacter le profil partenaire")

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_payment_return_completes_quick_checkout_after_bank_redirect(self):
        from interface import views

        original_gateway = views.payment_gateway
        views.payment_gateway = _PaymentReturnStub("succeeded")
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)

        response = self.client.get(
            reverse("interface:provider_payment_return"),
            data={
                "provider_id": self.provider.id,
                "quick_checkout_id": self.checkout.id,
                "payment_intent": "pi_success_1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "attente de confirmation manuelle")
        booking = Booking.objects.get()
        self.assertEqual(booking.status, "SUBMITTED")
        self.checkout.refresh_from_db()
        self.assertFalse(self.checkout.is_active)
        self.assertIsNotNone(self.checkout.completed_at)

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_payment_return_does_not_complete_quick_checkout_on_failed_status(self):
        from interface import views

        original_gateway = views.payment_gateway
        views.payment_gateway = _PaymentReturnStub("requires_payment_method")
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)

        response = self.client.get(
            reverse("interface:provider_payment_return"),
            data={
                "provider_id": self.provider.id,
                "quick_checkout_id": self.checkout.id,
                "payment_intent": "pi_failed_1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "carte")
        self.assertEqual(Booking.objects.count(), 0)
        self.checkout.refresh_from_db()
        self.assertTrue(self.checkout.is_active)
        self.assertIsNone(self.checkout.completed_at)


class QuickCheckoutModelValidationTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Diva", salon_zone="Paris")
        self.other_provider = Provider.objects.create(name="Mila", salon_zone="Lyon")
        self.service = Service.objects.create(
            provider=self.provider,
            name="Tresses",
            slug="tresses",
            base_price_cents=5000,
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

    def _build_checkout(self, **overrides):
        payload = {
            "provider": self.provider,
            "service": self.service,
            "client_name": "Léa",
            "client_email": "lea@example.com",
            "desired_date": timezone.now() + timedelta(days=2),
            "location_preference": "salon",
            "final_price_cents": 12000,
            "reservation_fee_cents": 3000,
        }
        payload.update(overrides)
        return QuickCheckoutPage(**payload)

    def test_full_clean_requires_client_address_for_domicile(self):
        checkout = self._build_checkout(location_preference="domicile", client_address="")

        with self.assertRaises(ValidationError) as exc_info:
            checkout.full_clean()

        self.assertIn("client_address", exc_info.exception.message_dict)

    def test_full_clean_requires_provider_salon_zone_for_salon_booking(self):
        self.provider.salon_zone = ""
        self.provider.save(update_fields=["salon_zone"])

        checkout = self._build_checkout(location_preference="salon")

        with self.assertRaises(ValidationError) as exc_info:
            checkout.full_clean()

        self.assertIn("provider", exc_info.exception.message_dict)

    def test_full_clean_requires_service_to_match_provider(self):
        checkout = self._build_checkout(provider=self.other_provider)

        with self.assertRaises(ValidationError) as exc_info:
            checkout.full_clean()

        self.assertIn("service", exc_info.exception.message_dict)

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

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_payment_intent_rejects_blocked_slot_before_payment_confirmation(self):
        from interface import views

        payment_stub = _PaymentStub()
        catalog_stub = _CatalogBlockedSlotStub()
        original_gateway = views.payment_gateway
        original_catalog = views.provider_catalog
        views.payment_gateway = payment_stub
        views.provider_catalog = catalog_stub
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)
        self.addCleanup(setattr, views, "provider_catalog", original_catalog)

        response = self.client.post(
            reverse("interface:provider_payment_intent"),
            data={
                "provider_id": self.provider.id,
                "service_id": self.service.id,
                "hair_length": "long",
                "general_adjustments": [],
                "meche": False,
                "location_preference": "salon",
                "desired_date": "2026-03-15T10:00",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "n'est plus disponible", status_code=409)
        self.assertEqual(payment_stub.calls, [])

    @override_settings(STRIPE_SECRET_KEY="sk_test", STRIPE_PUBLIC_KEY="pk_test")
    def test_payment_intent_rejects_blocked_slot_with_reason(self):
        from interface import views

        payment_stub = _PaymentStub()
        catalog_stub = _CatalogBlockedSlotStub(reason="Maëlle n'est pas disponible en semaine")
        original_gateway = views.payment_gateway
        original_catalog = views.provider_catalog
        views.payment_gateway = payment_stub
        views.provider_catalog = catalog_stub
        self.addCleanup(setattr, views, "payment_gateway", original_gateway)
        self.addCleanup(setattr, views, "provider_catalog", original_catalog)

        response = self.client.post(
            reverse("interface:provider_payment_intent"),
            data={
                "provider_id": self.provider.id,
                "service_id": self.service.id,
                "hair_length": "long",
                "general_adjustments": [],
                "meche": False,
                "location_preference": "salon",
                "desired_date": "2026-03-15T10:00",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertJSONEqual(
            response.content,
            {"error": "Créneau non disponible : Maëlle n'est pas disponible en semaine"},
        )
        self.assertEqual(payment_stub.calls, [])
