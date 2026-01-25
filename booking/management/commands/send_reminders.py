from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from booking.models import Booking, Provider
from chateaurose.domain.use_cases import send_reminder
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.email_notifier import EmailNotifier


class Command(BaseCommand):
    help = "Send reminder notifications for pending and confirmed bookings."

    @staticmethod
    def _parse_datetime(value, *, reference_tz):
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None

        if parsed.tzinfo is None and reference_tz is not None:
            return parsed.replace(tzinfo=reference_tz)
        return parsed

    @staticmethod
    def _format_price(cents: int) -> str:
        euros = cents / 100
        return f"{euros:.2f}".replace(".", ",") + " €"

    def handle(self, *args, **options):
        now = timezone.now()
        threshold = now - timedelta(hours=24)
        bookings = (
            Booking.objects.filter(status="SUBMITTED", created_at__lte=threshold)
            .select_related("provider")
            .order_by("provider_id", "created_at")
        )

        repository = DjangoBookingRepository()
        notifier = EmailNotifier()

        bookings_by_provider: dict[int, list[str]] = {}
        providers_by_id: dict[int, Provider] = {}
        for booking in bookings:
            bookings_by_provider.setdefault(booking.provider_id, []).append(booking.booking_id)
            providers_by_id.setdefault(booking.provider_id, booking.provider)

        for provider_id, booking_ids in bookings_by_provider.items():
            provider = providers_by_id[provider_id]
            last_sent = provider.pending_reminder_sent_at
            if last_sent and last_sent.date() == now.date():
                continue

            eligible = send_reminder.execute(
                provider_id=provider_id,
                booking_ids=booking_ids,
                now=now,
                booking_repository=repository,
                notifier=notifier,
            )
            if eligible:
                provider.pending_reminder_sent_at = now
                provider.save(update_fields=["pending_reminder_sent_at"])

        confirmed_bookings = Booking.objects.filter(
            status="CONFIRMED", client_reminder_sent_at__isnull=True
        )
        for booking in confirmed_bookings.iterator():
            effective_date = booking.proposed_date or booking.desired_date
            appointment_at = self._parse_datetime(
                effective_date, reference_tz=timezone.get_current_timezone()
            )
            if not appointment_at:
                continue
            reminder_at = appointment_at - timedelta(hours=24)
            if not (reminder_at <= now <= appointment_at):
                continue

            effective_price_cents = (
                booking.proposed_price_cents
                if booking.proposed_price_cents is not None
                else booking.estimated_price_cents
            )
            formatted_price = self._format_price(effective_price_cents)
            notifier.notify(
                booking.client_email,
                "Rappel: rendez-vous confirmé",
                "\n".join(
                    [
                        f"Bonjour {booking.client_name},",
                        "",
                        "Petit rappel pour ton rendez-vous confirmé.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {booking.location}",
                        f"- Tarif : {formatted_price}",
                        "",
                        "À très vite,",
                        "L'équipe Château Rose",
                    ]
                ),
            )
            booking.client_reminder_sent_at = now
            booking.save(update_fields=["client_reminder_sent_at"])
