from datetime import timedelta

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import InvalidState

SUBMITTED = "SUBMITTED"
PENDING_CLIENT_VALIDATION = "PENDING_CLIENT_VALIDATION"
CANCELLED = "CANCELLED"


def execute(
    *,
    booking_id: str,
    now,
    booking_repository,
    payment_gateway,
    notifier,
) -> BookingRequest:
    booking = booking_repository.get(booking_id)

    if booking.status in (CANCELLED,):
        return booking

    if booking.status in (SUBMITTED, PENDING_CLIENT_VALIDATION) and now - booking.created_at >= timedelta(hours=48):
        booking.status = CANCELLED
        payment_gateway.release_auth(booking.payment_auth_id)
        notifier.notify(
            booking.provider_id,
            "Demande expirée",
            "La demande a expiré après 48h sans confirmation.",
        )
        notifier.notify(
            booking.client_contact["phone"],
            "Demande expirée",
            "Votre demande a expiré après 48h sans confirmation.",
        )
        booking_repository.update(booking)
    return booking
