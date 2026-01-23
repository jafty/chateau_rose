from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from booking.models import Booking, Provider
from chateaurose.domain.use_cases import send_reminder
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.email_notifier import EmailNotifier


class Command(BaseCommand):
    help = "Send reminder notifications for pending bookings."

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
