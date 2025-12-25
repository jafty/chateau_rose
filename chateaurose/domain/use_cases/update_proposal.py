from chateaurose.domain.entities.booking import BookingRequest

PENDING_CLIENT_VALIDATION = "PENDING_CLIENT_VALIDATION"


def execute(
    *,
    booking_id: str,
    provider_id: str,
    new_price_cents: int,
    new_date: str,
    now=None,
    booking_repository,
    notifier,
) -> BookingRequest:
    booking = booking_repository.get(booking_id)
    if booking.provider_id != provider_id:
        raise PermissionError("Only owner provider can propose updates.")
    if booking.status not in ("SUBMITTED", PENDING_CLIENT_VALIDATION):
        raise InvalidState("Cannot propose update from terminal state")

    booking.status = PENDING_CLIENT_VALIDATION
    booking.proposed_price_cents = new_price_cents
    booking.proposed_date = new_date
    booking.updated_at = now or booking.created_at

    booking_repository.update(booking)

    notifier.notify(
        booking.client_contact["phone"],
        "Proposition de rendez-vous",
        "Une nouvelle proposition est disponible pour votre demande.",
    )
    return booking
from chateaurose.domain.exceptions import InvalidState, PermissionError
