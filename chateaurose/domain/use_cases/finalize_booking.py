from datetime import datetime, timedelta

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import InvalidState

CONFIRMED = "CONFIRMED"
CANCELLED = "CANCELLED"
PENDING_CLIENT_VALIDATION = "PENDING_CLIENT_VALIDATION"
SUBMITTED = "SUBMITTED"


def _parse_datetime(value, *, reference_tz):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None and reference_tz is not None:
        return parsed.replace(tzinfo=reference_tz)
    return parsed


def _compute_client_reminder_send_at(effective_date, *, reference_time):
    appointment_at = _parse_datetime(effective_date, reference_tz=reference_time.tzinfo)
    if appointment_at is None:
        return None
    reminder_at = appointment_at - timedelta(hours=24)
    return reminder_at if reminder_at > reference_time else reference_time


def execute(
    *,
    booking_id: str,
    actor: str,
    decision: str,
    now=None,
    booking_repository,
    payment_gateway,
    provider_directory,
    notifier,
    reminder_gateway=None,
) -> BookingRequest:
    booking = booking_repository.get(booking_id)

    effective_now = now or booking.created_at

    # Expired guard (48h)
    if now is not None and now - booking.created_at >= timedelta(hours=48):
        raise InvalidState("Booking has expired")

    if booking.status in (CONFIRMED, CANCELLED):
        return booking

    provider_contact = provider_directory.get_provider_contact(booking.provider_id)
    provider_name = provider_contact.get("name") or "La prestataire ou le prestataire"
    salon_address = provider_contact.get("salon_address") or "Adresse à confirmer"

    effective_date = booking.proposed_date or booking.desired_date
    effective_price_cents = (
        booking.proposed_price_cents
        if booking.proposed_price_cents is not None
        else booking.estimated_price_cents
    )
    euros = effective_price_cents / 100
    formatted_price = f"{euros:.2f}".replace(".", ",")
    formatted_price = f"{formatted_price} €"

    location_label = booking.location
    is_salon = booking.location_preference == "salon"
    client_address = booking.client_address or "Adresse à confirmer"
    provider_address_note = (
        "Adresse transmise uniquement pour ce rendez-vous, merci de la garder confidentielle."
    )
    client_address_note = "Cette information est partagée uniquement pour organiser le rendez-vous."

    if actor == "provider":
        if decision == "confirm" and booking.status == SUBMITTED:
            booking.status = CONFIRMED
            payment_gateway.capture_auth(booking.payment_auth_id)
            provider_location_lines = (
                ["La cliente ou le client se déplace au salon."]
                if is_salon
                else [f"Adresse de la cliente ou du client : {client_address}", provider_address_note]
            )
            client_location_lines = (
                [f"Adresse du salon : {salon_address}", client_address_note]
                if is_salon
                else ["La prestataire ou le prestataire se déplace jusqu'à toi."]
            )
            notifier.notify(
                booking.provider_id,
                "Rendez-vous confirmé",
                "\n".join(
                    [
                        f"Bonjour {provider_name},",
                        "",
                        "Merci, ton rendez-vous est confirmé.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        *provider_location_lines,
                        "",
                        "Belle journée,",
                        "L'équipe Château Rose",
                    ]
                ),
            )
            notifier.notify(
                booking.client_contact["email"],
                "Rendez-vous confirmé",
                "\n".join(
                    [
                        f"Bonjour {booking.client_contact['name']},",
                        "",
                        "Bonne nouvelle, ta réservation est confirmée.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        *client_location_lines,
                        "",
                        "À très vite,",
                        "L'équipe Château Rose",
                    ]
                ),
            )
            if reminder_gateway:
                send_at = _compute_client_reminder_send_at(effective_date, reference_time=effective_now)
                if send_at:
                    reminder_gateway.schedule(
                        recipient=booking.client_contact["email"],
                        send_at=send_at,
                        subject="Rappel: rendez-vous confirmé",
                        body="\n".join(
                            [
                                f"Bonjour {booking.client_contact['name']},",
                                "",
                                "Petit rappel pour ton rendez-vous confirmé.",
                                "Récapitulatif :",
                                f"- Date : {effective_date}",
                                f"- Lieu : {location_label}",
                                f"- Tarif : {formatted_price}",
                                "",
                                "À très vite,",
                                "L'équipe Château Rose",
                            ]
                        ),
                    )
        elif decision == "reject" and booking.status in (SUBMITTED, PENDING_CLIENT_VALIDATION):
            booking.status = CANCELLED
            payment_gateway.release_auth(booking.payment_auth_id)
            notifier.notify(
                booking.provider_id,
                "Demande annulée",
                "\n".join(
                    [
                        f"Bonjour {provider_name},",
                        "",
                        "Tu as bien annulé la demande.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        "À bientôt,",
                        "L'équipe Château Rose",
                    ]
                ),
            )
            notifier.notify(
                booking.client_contact["email"],
                "Demande annulée",
                "\n".join(
                    [
                        f"Bonjour {booking.client_contact['name']},",
                        "",
                        "La demande a été refusée par la prestataire ou le prestataire.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        "Si tu veux, tu peux déposer une nouvelle demande.",
                        "À bientôt,",
                        "L'équipe Château Rose",
                    ]
                ),
            )
        else:
            raise InvalidState("Invalid state for provider decision")

    elif actor == "client":
        if decision == "accept" and booking.status == PENDING_CLIENT_VALIDATION:
            booking.status = CONFIRMED
            payment_gateway.capture_auth(booking.payment_auth_id)
            provider_location_lines = (
                ["La cliente ou le client se déplace au salon."]
                if is_salon
                else [f"Adresse de la cliente ou du client : {client_address}", provider_address_note]
            )
            client_location_lines = (
                [f"Adresse du salon : {salon_address}", client_address_note]
                if is_salon
                else ["La prestataire ou le prestataire se déplace jusqu'à toi."]
            )
            notifier.notify(
                booking.provider_id,
                "Rendez-vous confirmé",
                "\n".join(
                    [
                        f"Bonjour {provider_name},",
                        "",
                        "La cliente ou le client a accepté la proposition.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        *provider_location_lines,
                        "",
                        "Belle journée,",
                        "L'équipe Château Rose",
                    ]
                ),
            )
            notifier.notify(
                booking.client_contact["email"],
                "Rendez-vous confirmé",
                "\n".join(
                    [
                        f"Bonjour {booking.client_contact['name']},",
                        "",
                        "Bonne nouvelle, ta réservation est confirmée.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        *client_location_lines,
                        "",
                        "À très vite,",
                        "L'équipe Château Rose",
                    ]
                ),
            )
            if reminder_gateway:
                send_at = _compute_client_reminder_send_at(effective_date, reference_time=effective_now)
                if send_at:
                    reminder_gateway.schedule(
                        recipient=booking.client_contact["email"],
                        send_at=send_at,
                        subject="Rappel: rendez-vous confirmé",
                        body="\n".join(
                            [
                                f"Bonjour {booking.client_contact['name']},",
                                "",
                                "Petit rappel pour ton rendez-vous confirmé.",
                                "Récapitulatif :",
                                f"- Date : {effective_date}",
                                f"- Lieu : {location_label}",
                                f"- Tarif : {formatted_price}",
                                "",
                                "À très vite,",
                                "L'équipe Château Rose",
                            ]
                        ),
                    )
        elif decision == "refuse" and booking.status == PENDING_CLIENT_VALIDATION:
            booking.status = CANCELLED
            payment_gateway.release_auth(booking.payment_auth_id)
            notifier.notify(
                booking.provider_id,
                "Demande annulée",
                "\n".join(
                    [
                        f"Bonjour {provider_name},",
                        "",
                        "La cliente ou le client a refusé la proposition.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        "À bientôt,",
                        "L'équipe Château Rose",
                    ]
                ),
            )
            notifier.notify(
                booking.client_contact["email"],
                "Demande annulée",
                "\n".join(
                    [
                        f"Bonjour {booking.client_contact['name']},",
                        "",
                        "Tu as refusé la proposition : la demande est annulée.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        "Si tu veux, tu peux déposer une nouvelle demande.",
                        "À bientôt,",
                        "L'équipe Château Rose",
                    ]
                ),
            )
        else:
            raise InvalidState("Invalid state for client decision")
    else:
        raise InvalidState("Unknown actor")

    booking.updated_at = effective_now
    booking_repository.update(booking)
    return booking
