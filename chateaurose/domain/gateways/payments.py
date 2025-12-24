from typing import Protocol


class PaymentGatewayPort(Protocol):
    def create_auth(self, amount_cents: int, currency: str, reference: str) -> str:
        ...

    def capture_auth(self, auth_id: str) -> None:
        ...

    def release_auth(self, auth_id: str) -> None:
        ...
