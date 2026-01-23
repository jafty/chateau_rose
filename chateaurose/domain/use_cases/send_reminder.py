from datetime import timedelta

from chateaurose.domain.entities.booking import BookingRequest

SUBMITTED = "SUBMITTED"


def execute(
    *,
    provider_id: str | int,
    booking_ids: list[str],
    now,
    booking_repository,
    notifier,
) -> list[BookingRequest]:
    bookings = [booking_repository.get(booking_id) for booking_id in booking_ids]
    eligible = [
        booking
        for booking in bookings
        if booking.status == SUBMITTED and now - booking.created_at >= timedelta(hours=24)
    ]
    if not eligible:
        return []

    lines = []
    for booking in eligible:
        lines.append(f"- Date : {booking.desired_date}")
        lines.append(f"  Lieu : {booking.location}")

    notifier.notify(
        provider_id,
        "Rappel: demandes en attente",
        "\n".join(
            [
                "Bonjour,",
                "",
                f"Tu as {len(eligible)} demande(s) en attente de réponse.",
                "Récapitulatif :",
                *lines,
                "",
                "À bientôt,",
                "L'équipe Château Rose",
            ]
        ),
    )
    return eligible
