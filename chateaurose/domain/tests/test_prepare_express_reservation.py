import pytest

from chateaurose.domain.entities.express_reservation import ExpressServiceChoice
from chateaurose.domain.exceptions import NotFound, ValidationError
from chateaurose.domain.use_cases import prepare_express_reservation


class StubCatalog:
    def __init__(self):
        self.choices = [
            ExpressServiceChoice("Tresses", "tresses", "Box Braids", "box-braids"),
            ExpressServiceChoice("Tresses", "tresses", "Knotless Braids", "knotless-braids"),
            ExpressServiceChoice("Locks", "locks", "Retwist", "retwist"),
        ]

    def list_visible_sub_services(self):
        return self.choices


class StubNotifier:
    def __init__(self):
        self.messages = []

    def notify(self, recipient, subject, body, reply_to=None):
        self.messages.append({"recipient": recipient, "subject": subject, "body": body, "reply_to": reply_to})


def test_list_grouped_choices_keeps_sub_services_under_parent_service():
    groups = prepare_express_reservation.list_grouped_choices(StubCatalog())

    assert groups == [
        {
            "service_name": "Tresses",
            "service_slug": "tresses",
            "choices": [
                {"label": "Box Braids", "value": "tresses/box-braids"},
                {"label": "Knotless Braids", "value": "tresses/knotless-braids"},
            ],
        },
        {
            "service_name": "Locks",
            "service_slug": "locks",
            "choices": [{"label": "Retwist", "value": "locks/retwist"}],
        },
    ]


def test_execute_builds_prefill_url_and_notifies_client():
    notifier = StubNotifier()

    target = prepare_express_reservation.execute(
        email=" CLIENT@Example.COM ",
        selected_choice="tresses/box-braids",
        catalog=StubCatalog(),
        notifier=notifier,
        base_url="https://chateau-rose.test",
    )

    assert target.service_name == "Tresses"
    assert target.sub_service_name == "Box Braids"
    assert target.reservation_url == (
        "https://chateau-rose.test/services/tresses/sous-services/box-braids/"
        "?prefill_email=client%40example.com#service-request"
    )
    assert len(notifier.messages) == 1
    assert notifier.messages[0]["recipient"] == "client@example.com"
    assert notifier.messages[0]["subject"] == "Ton lien de réservation Château Rose · Box Braids"
    assert notifier.messages[0]["reply_to"] is None
    assert "prefill_email=client%40example.com" in notifier.messages[0]["body"]


def test_execute_rejects_unknown_choice():
    with pytest.raises(NotFound):
        prepare_express_reservation.execute(
            email="client@example.com",
            selected_choice="tresses/inconnue",
            catalog=StubCatalog(),
            notifier=StubNotifier(),
        )


def test_execute_rejects_invalid_email():
    with pytest.raises(ValidationError):
        prepare_express_reservation.execute(
            email="not-an-email",
            selected_choice="tresses/box-braids",
            catalog=StubCatalog(),
            notifier=StubNotifier(),
        )
