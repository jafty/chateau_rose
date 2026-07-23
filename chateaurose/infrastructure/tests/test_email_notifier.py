from django.core import mail
from django.test import TestCase, override_settings

from booking.models import Provider
from chateaurose.infrastructure.email_notifier import EmailNotifier


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@example.com",
)
class EmailNotifierTests(TestCase):
    def setUp(self):
        self.notifier = EmailNotifier()

    def test_notify_resolves_provider_id_to_email(self):
        provider = Provider.objects.create(
            name="Maison Test",
            contact_email="owner@example.com",
        )

        delivered = self.notifier.notify(str(provider.id), "Rappel", "Contenu")

        assert delivered is True
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == ["owner@example.com"]
        assert message.subject == "Rappel"
        assert message.body == "Contenu"
        assert message.from_email == "no-reply@example.com"



    @override_settings(OPERATIONS_EMAIL="ops@example.com")
    def test_notify_routes_provider_id_to_operations_email_when_configured(self):
        provider = Provider.objects.create(
            name="Maison Ops",
            contact_email="provider@example.com",
        )

        self.notifier.notify(str(provider.id), "Rappel", "Contenu")

        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == ["ops@example.com"]

    def test_notify_sends_to_direct_email(self):
        delivered = self.notifier.notify("client@example.com", "Sujet", "Message")

        assert delivered is True
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == ["client@example.com"]
        assert message.subject == "Sujet"
        assert message.body == "Message"

    def test_notify_sets_reply_to_when_provided(self):
        self.notifier.notify(
            "client@example.com",
            "Sujet",
            "Message",
            reply_to="reply@example.com",
        )

        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.reply_to == ["reply@example.com"]

    def test_notify_skips_invalid_recipient(self):
        delivered = self.notifier.notify("not-an-email", "Sujet", "Message")

        assert delivered is False
        assert mail.outbox == []
