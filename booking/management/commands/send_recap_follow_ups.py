from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking
from chateaurose.infrastructure.email_notifier import EmailNotifier
from interface.models import ProviderBookingDraft

FOLLOW_UP_DELAY = timedelta(hours=24)


def _has_matching_validated_request(draft: ProviderBookingDraft) -> bool:
    """Match the reservation intent, not merely the email address.

    The creation-time boundary prevents an old booking from suppressing a new
    reservation by a returning client. Intent fields prevent two simultaneous,
    genuinely different reservations from suppressing one another.
    """
    payload = draft.payload or {}
    desired_date = str(payload.get("desired_date") or "")
    if not desired_date:
        return False

    bookings = Booking.objects.filter(
        client_email__iexact=draft.client_email.strip(),
        desired_date=desired_date,
        created_at__gte=draft.created_at,
    )
    if draft.provider_id:
        service_id = payload.get("service_id")
        if not service_id:
            return False
        return bookings.filter(
            booking_kind=Booking.KIND_PROVIDER_SELECTED,
            provider_id=draft.provider_id,
            service_id=service_id,
        ).exists()

    sub_service_id = payload.get("requested_marketing_sub_service_id")
    if not sub_service_id:
        return False
    return bookings.filter(
        booking_kind=Booking.KIND_GENERIC,
        requested_marketing_sub_service_id=sub_service_id,
    ).exists()


class Command(BaseCommand):
    help = "Send one follow-up for client recap links that were not validated after 24 hours."

    def handle(self, *args, **options):
        now = timezone.now()
        base_url = (
            getattr(settings, "SITE_URL", "") or "https://www.chateau-rose.fr"
        ).rstrip("/")
        notifier = EmailNotifier()
        sent = 0
        drafts = ProviderBookingDraft.objects.filter(
            source=ProviderBookingDraft.SOURCE_CLIENT,
            completed_at__isnull=True,
            follow_up_sent_at__isnull=True,
            created_at__lte=now - FOLLOW_UP_DELAY,
        ).order_by("created_at")

        for draft in drafts.iterator():
            if not draft.client_email or _has_matching_validated_request(draft):
                continue
            route = (
                "interface:provider_booking_recap"
                if draft.provider_id
                else "interface:generic_booking_recap"
            )
            recap_url = base_url + reverse(route, args=[draft.token])
            delivered = notifier.notify(
                draft.client_email,
                "Souhaites-tu toujours prendre rendez-vous ?",
                "\n".join(
                    [
                        f"Bonjour {draft.client_name.strip() or 'à toi'},",
                        "",
                        "Ton récapitulatif Château Rose est toujours disponible.",
                        "Si tu souhaites toujours prendre rendez-vous, vérifie les informations puis valide ta demande ici :",
                        recap_url,
                        "",
                        "Si ton projet a changé, tu peux simplement ignorer cet email : aucun autre rappel ne sera envoyé.",
                        "",
                        "L'équipe Château Rose",
                    ]
                ),
            )
            if delivered is False:
                self.stderr.write(
                    self.style.WARNING(
                        f"Follow-up for recap {draft.token} could not be sent; it will be retried."
                    )
                )
                continue
            draft.follow_up_sent_at = now
            draft.save(update_fields=["follow_up_sent_at", "updated_at"])
            sent += 1

        self.stdout.write(self.style.SUCCESS(f"{sent} recap follow-up email(s) sent."))
