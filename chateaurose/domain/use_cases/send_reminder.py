from datetime import timedelta

from chateaurose.domain.entities.booking import BookingRequest

SUBMITTED = "SUBMITTED"


def execute(
    *,
    booking_id: str,
    now,
    booking_repository,
    notifier,
) -> BookingRequest:
    booking = booking_repository.get(booking_id)
    if booking.status == SUBMITTED and now - booking.created_at >= timedelta(hours=24):
        notifier.notify(
            booking.provider_id,
            "Rappel: demande en attente",
            "\n".join(
                [
                    "Bonjour,",
                    "",
                    "Tu as une demande en attente de réponse.",
                    "Récapitulatif :",
                    f"- Date : {booking.desired_date}",
                    f"- Lieu : {booking.location}",
                    "",
                    "À bientôt,",
                    "L'équipe Château Rose",
                ]
            ),
        )
    return booking
