from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from booking.models import Provider


logger = logging.getLogger(__name__)


class EmailNotifier:
    def notify(self, recipient: str, subject: str, body: str) -> None:
        resolved = self._resolve_recipient(recipient)
        if not resolved:
            return

        try:
            if settings.BREVO_API_KEY:
                self._send_via_brevo(
                    recipient=resolved,
                    subject=subject,
                    body=body,
                )
            else:
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[resolved],
                    fail_silently=False,
                )
        except Exception:
            logger.warning(
                "Email notification failed",
                extra={"to": resolved, "subject": subject},
                exc_info=True,
            )
            return

        logger.info(
            "Email notification sent",
            extra={"to": resolved, "subject": subject},
        )

    @staticmethod
    def _send_via_brevo(recipient: str, subject: str, body: str) -> None:
        sender_email = settings.BREVO_SENDER_EMAIL or settings.DEFAULT_FROM_EMAIL
        payload = {
            "sender": {
                "email": sender_email,
                "name": settings.BREVO_SENDER_NAME or sender_email,
            },
            "to": [{"email": recipient}],
            "subject": subject,
            "textContent": body,
        }
        response = requests.post(
            settings.BREVO_API_URL,
            json=payload,
            headers={
                "api-key": settings.BREVO_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=settings.BREVO_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    def _resolve_recipient(self, recipient: str) -> str | None:
        if not recipient:
            return None

        raw = str(recipient).strip()
        if raw.isdigit():
            operations_email = (getattr(settings, "OPERATIONS_EMAIL", "") or "").strip()
            if operations_email and self._is_valid_email(operations_email):
                return operations_email

            provider_email = (
                Provider.objects.filter(id=raw)
                .values_list("contact_email", flat=True)
                .first()
            )
            if provider_email:
                cleaned = provider_email.strip()
                if cleaned:
                    return cleaned

        if self._is_valid_email(raw):
            return raw
        return None

    @staticmethod
    def _is_valid_email(value: str) -> bool:
        try:
            validate_email(value)
        except ValidationError:
            return False
        return True
