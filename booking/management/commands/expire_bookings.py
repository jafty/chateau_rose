from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from booking.models import Booking
from chateaurose.domain.use_cases import expire_booking
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.email_notifier import EmailNotifier
from chateaurose.infrastructure.stripe_gateway import StripePaymentGateway


class Command(BaseCommand):
    help = "Expire stale booking requests and release uncaptured payment intents."

    def handle(self, *args, **options):
        now = timezone.now()
        threshold = now - expire_booking.EXPIRATION_DELAY

        booking_ids = list(
            Booking.objects.filter(
                status__in=(expire_booking.SUBMITTED, expire_booking.PENDING_CLIENT_VALIDATION, expire_booking.AWAITING_ALTERNATIVE_PROVIDER),
                created_at__lte=threshold,
            )
            .order_by("created_at")
            .values_list("booking_id", flat=True)
        )

        if not booking_ids:
            self.stdout.write(self.style.SUCCESS("No booking to expire."))
            return

        repository = DjangoBookingRepository()
        payment_gateway = StripePaymentGateway()
        notifier = EmailNotifier()

        expired_count = 0
        for booking_id in booking_ids:
            result = expire_booking.execute(
                booking_id=booking_id,
                now=now,
                booking_repository=repository,
                payment_gateway=payment_gateway,
                notifier=notifier,
                operations_email=(getattr(settings, "OPERATIONS_EMAIL", "") or "").strip() or None,
            )
            if result.status == expire_booking.CANCELLED:
                expired_count += 1

        self.stdout.write(self.style.SUCCESS(f"Expired {expired_count} booking(s)."))
