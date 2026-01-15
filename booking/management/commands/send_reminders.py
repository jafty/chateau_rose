from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from booking.models import Booking
from chateaurose.domain.use_cases import send_reminder
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.twilio_notifier import TwilioNotifier


class Command(BaseCommand):
    help = "Send reminder notifications for pending bookings."

    def handle(self, *args, **options):
        now = timezone.now()
        threshold = now - timedelta(hours=24)
        bookings = Booking.objects.filter(status="SUBMITTED", created_at__lte=threshold)

        repository = DjangoBookingRepository()
        notifier = TwilioNotifier()

        for booking in bookings:
            send_reminder.execute(
                booking_id=booking.booking_id,
                now=now,
                booking_repository=repository,
                notifier=notifier,
            )
