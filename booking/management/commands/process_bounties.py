from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from booking.models import Booking, BookingOffer, BookingOpportunity
from chateaurose.infrastructure.bounty_service import open_for_booking
from chateaurose.infrastructure.email_notifier import EmailNotifier
from chateaurose.infrastructure.stripe_gateway import StripePaymentGateway


class Command(BaseCommand):
    help = "Open due bounties and expire unanswered opportunities/offers."

    def handle(self, *args, **options):
        now = timezone.now()
        generic_ids = Booking.objects.filter(
            status=Booking.STATUS_WAITING_PROVIDER_ASSIGNMENT
        ).values_list("booking_id", flat=True)
        expired_provider_ids = Booking.objects.filter(
            status=Booking.STATUS_SUBMITTED, initial_provider_deadline_at__lte=now
        ).values_list("booking_id", flat=True)
        alternative_ids = Booking.objects.filter(
            status=Booking.STATUS_AWAITING_ALTERNATIVE_PROVIDER
        ).values_list("booking_id", flat=True)
        for booking_id in generic_ids:
            open_for_booking(booking_id, reason=BookingOpportunity.REASON_GENERIC)
        for booking_id in expired_provider_ids:
            open_for_booking(
                booking_id, reason=BookingOpportunity.REASON_PROVIDER_TIMEOUT
            )
        for booking_id in alternative_ids:
            open_for_booking(
                booking_id, reason=BookingOpportunity.REASON_PROVIDER_REJECTED
            )

        notifier, payments = EmailNotifier(), StripePaymentGateway()
        for opportunity in BookingOpportunity.objects.filter(
            status=BookingOpportunity.STATUS_OPEN, response_deadline_at__lte=now
        ).select_related("booking"):
            with transaction.atomic():
                opportunity = BookingOpportunity.objects.select_for_update().get(
                    pk=opportunity.pk
                )
                if opportunity.status != BookingOpportunity.STATUS_OPEN:
                    continue
                opportunity.status, opportunity.closed_at = (
                    BookingOpportunity.STATUS_EXPIRED,
                    now,
                )
                opportunity.save(update_fields=("status", "closed_at"))
                booking = opportunity.booking
                booking.status, booking.updated_at = Booking.STATUS_CANCELLED, now
                booking.save(update_fields=("status", "updated_at"))
                if booking.payment_auth_id:
                    payments.release_auth(booking.payment_auth_id)
                    booking.payment_status = Booking.PAYMENT_STATUS_RELEASED
                    booking.save(update_fields=("payment_status",))
                notifier.notify(
                    booking.client_email,
                    "Demande annulée",
                    "Aucune prestataire n'a proposé de prendre en charge ta demande dans le délai prévu. Ton autorisation de paiement a été libérée.",
                )

        for offer in BookingOffer.objects.filter(
            status=BookingOffer.STATUS_PENDING_CLIENT, client_deadline_at__lte=now
        ).select_related("opportunity__booking"):
            with transaction.atomic():
                offer = BookingOffer.objects.select_for_update().get(pk=offer.pk)
                if offer.status != BookingOffer.STATUS_PENDING_CLIENT:
                    continue
                offer.status, offer.decided_at = BookingOffer.STATUS_EXPIRED, now
                offer.save(update_fields=("status", "decided_at"))
                booking = offer.opportunity.booking
                booking.status, booking.updated_at = Booking.STATUS_CANCELLED, now
                booking.save(update_fields=("status", "updated_at"))
                if booking.payment_auth_id:
                    payments.release_auth(booking.payment_auth_id)
                    booking.payment_status = Booking.PAYMENT_STATUS_RELEASED
                    booking.save(update_fields=("payment_status",))
                notifier.notify(
                    booking.client_email,
                    "Proposition expirée",
                    "La proposition n'a pas été acceptée dans le délai prévu. La demande est annulée et ton autorisation de paiement a été libérée.",
                )
        self.stdout.write(self.style.SUCCESS("Bounties processed."))
