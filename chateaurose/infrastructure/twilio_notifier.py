from __future__ import annotations

import logging

from django.conf import settings
from twilio.rest import Client

from booking.models import Provider


logger = logging.getLogger(__name__)


class TwilioNotifier:
    def __init__(self):
        self._client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    def notify(self, recipient: str, subject: str, body: str) -> None:
        resolved = self._resolve_recipient(recipient)
        if not resolved:
            return

        message_body = f"{subject}\n{body}".strip()
        if settings.TWILIO_ENABLE_SMS and settings.TWILIO_SMS_FROM:
            message = self._client.messages.create(
                body=message_body,
                from_=settings.TWILIO_SMS_FROM,
                to=resolved.sms,
            )
            logger.info(
                "Twilio SMS sent",
                extra={
                    "from": settings.TWILIO_SMS_FROM,
                    "to": resolved.sms,
                    "sid": getattr(message, "sid", None),
                    "body": message_body,
                },
            )
        if settings.TWILIO_ENABLE_WHATSAPP and settings.TWILIO_WHATSAPP_FROM:
            message = self._client.messages.create(
                body=message_body,
                from_=settings.TWILIO_WHATSAPP_FROM,
                to=resolved.whatsapp,
            )
            logger.info(
                "Twilio WhatsApp sent",
                extra={
                    "from": settings.TWILIO_WHATSAPP_FROM,
                    "to": resolved.whatsapp,
                    "sid": getattr(message, "sid", None),
                    "body": message_body,
                },
            )

    def _resolve_recipient(self, recipient: str) -> _ResolvedRecipient | None:
        if not recipient:
            return None

        raw = str(recipient).strip()
        if raw.isdigit():
            provider_phone = (
                Provider.objects.filter(id=raw)
                .values_list("contact_phone", flat=True)
                .first()
            )
            if provider_phone:
                cleaned = provider_phone.strip()
                if cleaned:
                    return _ResolvedRecipient(sms=cleaned, whatsapp=f"whatsapp:{cleaned}")

        if raw.startswith("whatsapp:"):
            phone = raw.removeprefix("whatsapp:").strip()
            if not phone:
                return None
            return _ResolvedRecipient(sms=phone, whatsapp=f"whatsapp:{phone}")

        normalized = raw.replace(" ", "").replace("-", "")
        if normalized.startswith("+") or normalized.isdigit():
            return _ResolvedRecipient(sms=normalized, whatsapp=f"whatsapp:{normalized}")
        return None


class _ResolvedRecipient:
    def __init__(self, *, sms: str, whatsapp: str):
        self.sms = sms
        self.whatsapp = whatsapp
