from unittest.mock import patch

import stripe
from django.test import SimpleTestCase, override_settings

from chateaurose.infrastructure.stripe_gateway import StripePaymentGateway


@override_settings(STRIPE_SECRET_KEY="sk_test")
class StripeGatewayTests(SimpleTestCase):
    def test_release_auth_is_noop_for_free_checkout_reference(self):
        gateway = StripePaymentGateway()

        with patch("chateaurose.infrastructure.stripe_gateway.stripe.PaymentIntent.cancel") as cancel_mock:
            gateway.release_auth("free_quick_checkout_123")

        cancel_mock.assert_not_called()

    def test_release_auth_ignores_already_canceled_payment_intent(self):
        gateway = StripePaymentGateway()

        error = stripe.InvalidRequestError(
            message=(
                "You cannot cancel this PaymentIntent because it has a status of canceled. "
                "Only a PaymentIntent with one of the following statuses may be canceled"
            ),
            param=None,
            code="payment_intent_unexpected_state",
        )

        with patch(
            "chateaurose.infrastructure.stripe_gateway.stripe.PaymentIntent.cancel",
            side_effect=error,
        ):
            gateway.release_auth("pi_123")

    def test_release_auth_re_raises_unexpected_stripe_errors(self):
        gateway = StripePaymentGateway()

        error = stripe.InvalidRequestError(
            message="Random Stripe issue",
            param=None,
            code="rate_limit",
        )

        with patch(
            "chateaurose.infrastructure.stripe_gateway.stripe.PaymentIntent.cancel",
            side_effect=error,
        ):
            with self.assertRaises(stripe.InvalidRequestError):
                gateway.release_auth("pi_123")
