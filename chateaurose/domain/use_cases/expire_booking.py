from datetime import timedelta

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import InvalidState

SUBMITTED = "SUBMITTED"
PENDING_CLIENT_VALIDATION = "PENDING_CLIENT_VALIDATION"
CANCELLED = "CANCELLED"
EXPIRATION_DELAY = timedelta(hours=72)


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

    if booking.status in (SUBMITTED, PENDING_CLIENT_VALIDATION) and now - booking.created_at >= EXPIRATION_DELAY:
        booking.status = CANCELLED
        booking.updated_at = now
        payment_gateway.release_auth(booking.payment_auth_id)
        euros = booking.estimated_price_cents / 100
        formatted_price = f"{euros:.2f}".replace(".", ",")
        formatted_price = f"{formatted_price} €"
        effective_date = booking.proposed_date or booking.desired_date
        notifier.notify(
            booking.provider_id,
            "Demande expirée",
            "\n".join(
                [
                    "Bonjour,",
                    "",
                    "La demande a expiré faute de confirmation.",
                    "Récapitulatif :",
                    f"- Date : {effective_date}",
                    f"- Lieu : {booking.location}",
                    f"- Tarif : {formatted_price}",
                    "",
                    "À bientôt,",
                    "L'équipe Château Rose",
                ]
            ),
        )
        notifier.notify(
            booking.client_contact["email"],
            "Demande expirée",
            "\n".join(
                [
                    f"Bonjour {booking.client_contact['name']},",
                    "",
                    "La demande a expiré faute de confirmation.",
                    "Récapitulatif :",
                    f"- Date : {effective_date}",
                    f"- Lieu : {booking.location}",
                    f"- Tarif : {formatted_price}",
                    "",
                    "Si tu veux, tu peux déposer une nouvelle demande.",
                    "À bientôt,",
                    "L'équipe Château Rose",
                ]
            ),
        )
        booking_repository.update(booking)
    return booking
