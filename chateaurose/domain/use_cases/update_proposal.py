from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import InvalidState, PermissionError, ValidationError

PENDING_CLIENT_VALIDATION = "PENDING_CLIENT_VALIDATION"


def execute(
    *,
    booking_id: str,
    provider_id: str,
    new_price_cents: int | None,
    new_date: str | None,
    client_control_url: str | None,
    now=None,
    booking_repository,
    provider_directory,
    notifier,
) -> BookingRequest:
    normalized_date = new_date.strip() if isinstance(new_date, str) else None
    if new_price_cents is None and not normalized_date:
        raise ValidationError("Merci d'indiquer un nouveau tarif ou une date.")
    if not client_control_url:
        raise ValidationError("Missing client control link.")

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

    provider_contact = provider_directory.get_provider_contact(provider_id)
    provider_name = provider_contact.get("name") or "La prestataire ou le prestataire"
    provider_phone = provider_contact.get("phone") or "Non renseigné"
    provider_email = provider_contact.get("email") or "Non renseigné"

    proposed_date = booking.proposed_date or booking.desired_date or "À confirmer"
    if new_price_cents is None:
        euros = booking.estimated_price_cents / 100
        proposed_price = f"{euros:.2f}".replace(".", ",")
        proposed_price = f"{proposed_price} €"
    else:
        euros = booking.proposed_price_cents / 100
        proposed_price = f"{euros:.2f}".replace(".", ",")
        proposed_price = f"{proposed_price} €"

    message_lines = [
        f"Bonjour {booking.client_contact['name']},",
        "",
        f"{provider_name} a une nouvelle proposition pour ta demande.",
        "Voici les nouveaux détails :",
        f"- Date proposée : {proposed_date}",
        f"- Tarif proposé : {proposed_price}",
        "",
        "Tu peux accepter ou refuser la proposition depuis ton espace de suivi :",
        client_control_url,
        "",
        "Besoin d'échanger avant de décider ?",
        f"- Téléphone : {provider_phone}",
        f"- Email : {provider_email}",
        "",
        "Merci et à très vite,",
        "L'équipe Château Rose",
    ]

    notifier.notify(
        booking.client_contact["email"],
        "Proposition de rendez-vous",
        "\n".join(message_lines),
    )
    return booking
