from datetime import datetime

from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking, ReviewInvitation
from chateaurose.domain.services.reviews import BookingReviewState, invitation_due
from chateaurose.infrastructure.email_notifier import EmailNotifier
from django.conf import settings


class Command(BaseCommand):
    help = "Send post-appointment verified review requests and restrained reminders."

    @staticmethod
    def _parse_datetime(value):
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    def handle(self, *args, **options):
        now = timezone.now()
        notifier = EmailNotifier()
        sent = 0
        bookings = Booking.objects.filter(status=Booking.STATUS_CONFIRMED).select_related("provider", "service")
        for booking in bookings.iterator():
            invitation, _ = ReviewInvitation.objects.get_or_create(booking=booking)
            appointment_at = self._parse_datetime(booking.proposed_date or booking.desired_date)
            state = BookingReviewState(
                status=booking.status,
                appointment_at=appointment_at,
                has_review=hasattr(booking, "verified_review"),
                has_incident_response=bool(invitation.incident_response_recorded_at),
                invitations_sent=invitation.sent_count,
                last_invitation_sent_at=invitation.last_sent_at,
            )
            due, _reason = invitation_due(state, now)
            if not due:
                continue
            review_url = (getattr(settings, "SITE_URL", "") or "https://www.chateau-rose.fr").rstrip("/") + reverse("interface:leave_verified_review", args=[invitation.token])
            delivered = notifier.notify(
                booking.client_email,
                "Ton avis sur ta prestation Château Rose",
                "\n".join([
                    f"Bonjour {booking.client_name},",
                    "",
                    "Merci d'avoir réservé via Château Rose. Si ton rendez-vous a bien eu lieu, tu peux laisser une note de 1 à 5 et un court commentaire :",
                    review_url,
                    "",
                    "Si la prestation n'a pas eu lieu ou si quelque chose s'est mal passé, réponds simplement à cet email : nous traiterons la situation avant tout nouvel envoi.",
                    "",
                    "L'équipe Château Rose",
                ]),
            )
            if not delivered:
                self.stderr.write(self.style.WARNING(f"Review request email not sent for booking {booking.booking_id}."))
                continue
            invitation.sent_count += 1
            invitation.last_sent_at = now
            invitation.save(update_fields=["sent_count", "last_sent_at", "updated_at"])
            sent += 1
        self.stdout.write(self.style.SUCCESS(f"{sent} review request email(s) sent."))
