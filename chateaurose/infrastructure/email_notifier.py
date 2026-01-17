from __future__ import annotations

import logging

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

    def _resolve_recipient(self, recipient: str) -> str | None:
        if not recipient:
            return None

        raw = str(recipient).strip()
        if raw.isdigit():
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
