from datetime import timedelta

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import InvalidState

CONFIRMED = "CONFIRMED"
CANCELLED = "CANCELLED"
PENDING_CLIENT_VALIDATION = "PENDING_CLIENT_VALIDATION"
SUBMITTED = "SUBMITTED"


def execute(
    *,
    booking_id: str,
    actor: str,
    decision: str,
    now=None,
    booking_repository,
    payment_gateway,
    notifier,
) -> BookingRequest:
    booking = booking_repository.get(booking_id)

    effective_now = now or booking.created_at

    # Expired guard (48h)
    if now is not None and now - booking.created_at >= timedelta(hours=48):
        raise InvalidState("Booking has expired")

    if booking.status in (CONFIRMED, CANCELLED):
        return booking

    if actor == "provider":
        if decision == "confirm" and booking.status == SUBMITTED:
            booking.status = CONFIRMED
            payment_gateway.capture_auth(booking.payment_auth_id)
            notifier.notify(
                booking.provider_id,
                "Rendez-vous confirmé",
                "Vous avez confirmé le rendez-vous.",
            )
            notifier.notify(
                booking.client_contact["phone"],
                "Rendez-vous confirmé",
                "Votre rendez-vous est confirmé.",
            )
        elif decision == "reject" and booking.status in (SUBMITTED, PENDING_CLIENT_VALIDATION):
            booking.status = CANCELLED
            payment_gateway.release_auth(booking.payment_auth_id)
            notifier.notify(
                booking.provider_id,
                "Demande annulée",
                "Vous avez annulé la demande.",
            )
            notifier.notify(
                booking.client_contact["phone"],
                "Demande annulée",
                "Votre demande a été refusée.",
            )
        else:
            raise InvalidState("Invalid state for provider decision")

    elif actor == "client":
        if decision == "accept" and booking.status == PENDING_CLIENT_VALIDATION:
            booking.status = CONFIRMED
            payment_gateway.capture_auth(booking.payment_auth_id)
            notifier.notify(
                booking.provider_id,
                "Rendez-vous confirmé",
                "La cliente a accepté la proposition.",
            )
            notifier.notify(
                booking.client_contact["phone"],
                "Rendez-vous confirmé",
                "Votre rendez-vous est confirmé.",
            )
        elif decision == "refuse" and booking.status == PENDING_CLIENT_VALIDATION:
            booking.status = CANCELLED
            payment_gateway.release_auth(booking.payment_auth_id)
            notifier.notify(
                booking.provider_id,
                "Demande annulée",
                "La cliente a refusé la proposition.",
            )
            notifier.notify(
                booking.client_contact["phone"],
                "Demande annulée",
                "Votre demande a été refusée.",
            )
        else:
            raise InvalidState("Invalid state for client decision")
    else:
        raise InvalidState("Unknown actor")

    booking.updated_at = effective_now
    booking_repository.update(booking)
    return booking
