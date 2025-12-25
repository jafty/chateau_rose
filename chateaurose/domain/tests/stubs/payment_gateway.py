class InMemoryPaymentGateway:
    def __init__(self):
        self.auth_calls = []
        self.capture_calls = []
        self.release_calls = []

    def create_auth(self, amount_cents, currency, reference):
        auth_id = f"auth_{len(self.auth_calls) + 1}"
        self.auth_calls.append(
            {"amount_cents": amount_cents, "currency": currency, "reference": reference, "id": auth_id}
        )
        return auth_id

    def capture_auth(self, auth_id):
        self.capture_calls.append({"auth_id": auth_id})

    def release_auth(self, auth_id):
        self.release_calls.append({"auth_id": auth_id})
