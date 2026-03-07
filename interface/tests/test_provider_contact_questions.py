from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from booking.models import Provider


class ProviderQuestionViewTests(TestCase):
    def test_question_is_sent_to_support(self):
        provider = Provider.objects.create(
            name="Nina",
            contact_email="nina@example.com",
        )

        with patch("interface.views.notifier.notify") as notify_mock:
            response = self.client.post(
                reverse("interface:provider_detail", args=[provider.id]),
                data={
                    "question_form": "1",
                    "client_name": "Aya",
                    "client_email": "aya@example.com",
                    "message": "Bonjour, as-tu une place samedi ?",
                },
            )

        self.assertRedirects(
            response,
            reverse("interface:thank_you_question"),
            fetch_redirect_response=False,
        )
        notify_mock.assert_called_once()
        recipient, subject, body = notify_mock.call_args[0]
        self.assertEqual(recipient, "japhet@chateau-rose.fr")
        self.assertEqual(subject, "Question depuis le profil de Nina")
        self.assertIn("Destinataire : Château Rose", body)
