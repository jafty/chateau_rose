from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from booking.models import Provider


logger = logging.getLogger(__name__)


class EmailNotifier:
    def notify(self, recipient: str, subject: str, body: str, reply_to: str | list[str] | tuple[str, ...] | None = None) -> bool:
        resolved = self._resolve_recipient(recipient)
        if not resolved:
            logger.warning(
                "Email notification skipped because the recipient is invalid",
                extra={"to": recipient, "subject": subject},
            )
            return False

        resolved_reply_to = self._resolve_reply_to(reply_to)

        try:
            if settings.BREVO_API_KEY:
                self._send_via_brevo(
                    recipient=resolved,
                    subject=subject,
                    body=body,
                    reply_to=resolved_reply_to,
                )
            else:
                message = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[resolved],
                    reply_to=resolved_reply_to or None,
                )
                message.send(fail_silently=False)
        except Exception:
            logger.warning(
                "Email notification failed",
                extra={"to": resolved, "subject": subject},
                exc_info=True,
            )
            return False

        logger.info(
            "Email notification sent",
            extra={"to": resolved, "subject": subject},
        )
        return True

    @staticmethod
    def _send_via_brevo(
        recipient: str,
        subject: str,
        body: str,
        reply_to: list[str] | None = None,
    ) -> None:
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
        if reply_to:
            payload["replyTo"] = {"email": reply_to[0]}
            if len(reply_to) > 1:
                payload["cc"] = [{"email": email} for email in reply_to[1:] if email != recipient]
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

    def _resolve_reply_to(self, reply_to: str | list[str] | tuple[str, ...] | None) -> list[str]:
        if not reply_to:
            return []
        values = reply_to if isinstance(reply_to, (list, tuple)) else [reply_to]
        resolved = []
        for value in values:
            email = self._resolve_provider_or_email(value)
            if email and email not in resolved:
                resolved.append(email)
        return resolved

    def _resolve_provider_or_email(self, value: str) -> str | None:
        if not value:
            return None
        cleaned = str(value).strip()
        if not cleaned:
            return None
        if cleaned.isdigit():
            provider_email = (
                Provider.objects.filter(id=cleaned)
                .values_list("contact_email", flat=True)
                .first()
            )
            if provider_email and self._is_valid_email(provider_email.strip()):
                return provider_email.strip()
        if self._is_valid_email(cleaned):
            return cleaned
        return None
