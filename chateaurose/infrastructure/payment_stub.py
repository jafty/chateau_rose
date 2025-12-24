class PaymentGatewayStub:
    def __init__(self):
        self.auths = []
        self.captures = []
        self.releases = []

    def create_auth(self, amount_cents, currency, reference):
        auth_id = f"auth_{len(self.auths) + 1}"
        self.auths.append({"amount_cents": amount_cents, "currency": currency, "reference": reference, "id": auth_id})
        return auth_id

    def capture_auth(self, auth_id):
        self.captures.append({"auth_id": auth_id})

    def release_auth(self, auth_id):
        self.releases.append({"auth_id": auth_id})
