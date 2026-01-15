import stripe
from django.conf import settings


class StripePaymentGateway:
    def __init__(self, api_key: str | None = None):
        stripe.api_key = api_key or settings.STRIPE_SECRET_KEY

    def create_auth(self, amount_cents: int, currency: str, reference: str) -> str:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency.lower(),
            capture_method=settings.STRIPE_CAPTURE_METHOD,
            metadata={"reference": reference},
        )
        return intent.id

    def capture_auth(self, auth_id: str) -> None:
        stripe.PaymentIntent.capture(auth_id)

    def release_auth(self, auth_id: str) -> None:
        stripe.PaymentIntent.cancel(auth_id)
