from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from booking.models import Provider
from interface.forms import ProviderQuestionForm


class ProviderQuestionFormTests(TestCase):
    def test_provider_target_unavailable_without_provider_email(self):
        provider = Provider.objects.create(name="Test Provider")
        form = ProviderQuestionForm(
            data={
                "client_name": "Aya",
                "client_email": "aya@example.com",
                "target": ProviderQuestionForm.TARGET_PROVIDER,
                "subject": "Question",
                "message": "Bonjour",
            },
            provider=provider,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "La prestataire ou le prestataire ne reçoit pas encore les questions par email.",
            form.errors.get("target", []),
        )


class ProviderQuestionViewTests(TestCase):
    def test_question_is_sent_to_provider_when_selected(self):
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
                    "target": ProviderQuestionForm.TARGET_PROVIDER,
                    "subject": "Disponibilité samedi",
                    "message": "Bonjour, as-tu une place samedi ?",
                },
            )

        self.assertRedirects(response, f"{reverse('interface:provider_detail', args=[provider.id])}#provider-question", fetch_redirect_response=False)
        notify_mock.assert_called_once()
        recipient = notify_mock.call_args[0][0]
        self.assertEqual(recipient, "nina@example.com")

    def test_question_is_sent_to_support_when_selected(self):
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
                    "target": ProviderQuestionForm.TARGET_CHATEAU_ROSE,
                    "subject": "Question paiement",
                    "message": "Comment fonctionne l'empreinte bancaire ?",
                },
            )

        self.assertRedirects(response, f"{reverse('interface:provider_detail', args=[provider.id])}#provider-question", fetch_redirect_response=False)
        notify_mock.assert_called_once()
        recipient = notify_mock.call_args[0][0]
        self.assertEqual(recipient, "japhet.situmonana@gmail.com")
