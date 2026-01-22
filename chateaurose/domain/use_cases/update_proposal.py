from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import InvalidState, PermissionError, ValidationError

PENDING_CLIENT_VALIDATION = "PENDING_CLIENT_VALIDATION"


def execute(
    *,
    booking_id: str,
    provider_id: str,
    new_price_cents: int | None,
    new_date: str | None,
    now=None,
    booking_repository,
    notifier,
) -> BookingRequest:
    normalized_date = new_date.strip() if isinstance(new_date, str) else None
    if new_price_cents is None and not normalized_date:
        raise ValidationError("Merci d'indiquer un nouveau tarif ou une date.")

    booking = booking_repository.get(booking_id)
    if booking.provider_id != provider_id:
        raise PermissionError("Only owner provider can propose updates.")
    if booking.status not in ("SUBMITTED", PENDING_CLIENT_VALIDATION):
        raise InvalidState("Cannot propose update from terminal state")

    booking.status = PENDING_CLIENT_VALIDATION
    if new_price_cents is not None:
        booking.proposed_price_cents = new_price_cents
    if normalized_date:
        booking.proposed_date = normalized_date
    booking.updated_at = now or booking.created_at

    booking_repository.update(booking)

    notifier.notify(
        booking.client_contact["email"],
        "Proposition de rendez-vous",
        "Une nouvelle proposition est disponible pour votre demande.",
    )
    return booking
