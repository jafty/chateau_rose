from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import InvalidState, PermissionError, ValidationError

PENDING_CLIENT_VALIDATION = "PENDING_CLIENT_VALIDATION"


def _format_euros(amount_cents: int) -> str:
    euros = amount_cents / 100
    return f"{euros:.2f}".replace(".", ",") + " €"


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
    deposit_percentage = provider_contact.get("deposit_percentage") or 30

    proposed_date = booking.proposed_date or booking.desired_date or "À confirmer"
    if new_price_cents is None:
        effective_price_cents = booking.estimated_price_cents
    else:
        effective_price_cents = booking.proposed_price_cents
    proposed_price = _format_euros(effective_price_cents)
    reservation_fee_cents = round(effective_price_cents * deposit_percentage / 100)
    remaining_cents = max(effective_price_cents - reservation_fee_cents, 0)

    message_lines = [
        f"Bonjour {booking.client_contact['name']},",
        "",
        f"{provider_name} a une nouvelle proposition pour ta demande.",
        "Voici les nouveaux détails :",
        f"- Date proposée : {proposed_date}",
        f"- Tarif proposé : {proposed_price}",
        "",
        "Paiement :",
        f"- Empreinte bancaire déjà validée : {_format_euros(reservation_fee_cents)} (pas encore débités)",
        f"- Montant débité si tu acceptes : {_format_euros(reservation_fee_cents)}",
        f"- Reste à régler directement au salon/prestataire : {_format_euros(remaining_cents)}",
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
