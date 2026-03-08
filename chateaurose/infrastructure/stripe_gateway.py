import stripe
from django.conf import settings


class StripePaymentGateway:
    FREE_AUTH_PREFIX = "free_quick_checkout_"

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

    def create_payment_intent(self, amount_cents: int, currency: str, reference: str) -> dict:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency.lower(),
            capture_method=settings.STRIPE_CAPTURE_METHOD,
            metadata={"reference": reference},
        )
        return {"id": intent.id, "client_secret": intent.client_secret}

    def retrieve_payment_intent(self, intent_id: str) -> dict:
        intent = stripe.PaymentIntent.retrieve(intent_id)
        return {"id": intent.id, "status": intent.status}

    def capture_auth(self, auth_id: str) -> None:
        if auth_id.startswith(self.FREE_AUTH_PREFIX):
            return
        stripe.PaymentIntent.capture(auth_id)

    def release_auth(self, auth_id: str) -> None:
        if auth_id.startswith(self.FREE_AUTH_PREFIX):
            return
        stripe.PaymentIntent.cancel(auth_id)
