from datetime import datetime, timedelta

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import InvalidState
from chateaurose.domain.use_cases.expire_booking import EXPIRATION_DELAY

CONFIRMED = "CONFIRMED"
CANCELLED = "CANCELLED"
PENDING_CLIENT_VALIDATION = "PENDING_CLIENT_VALIDATION"
SUBMITTED = "SUBMITTED"


def _format_euros(amount_cents: int) -> str:
    euros = amount_cents / 100
    return f"{euros:.2f}".replace(".", ",") + " €"


def _payment_lines(total_cents: int, *, captured: bool, deposit_percentage: int = 30) -> list[str]:
    reservation_fee_cents = round(total_cents * deposit_percentage / 100)
    remaining_cents = max(total_cents - reservation_fee_cents, 0)
    if captured:
        return [
            "Paiement :",
            f"- Frais de réservation débités : {_format_euros(reservation_fee_cents)}",
            f"- Reste à régler chez la prestataire : {_format_euros(remaining_cents)}",
        ]
    return [
        "Paiement :",
        f"- Empreinte bancaire déjà validée : {_format_euros(reservation_fee_cents)} (pas encore débités)",
        f"- Montant qui sera débité à la confirmation : {_format_euros(reservation_fee_cents)}",
        f"- Reste à régler chez la prestataire après confirmation : {_format_euros(remaining_cents)}",
    ]


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
    operations_email: str | None = None,
) -> BookingRequest:
    booking = booking_repository.get(booking_id)

    effective_now = now or booking.created_at

    # Expired guard: applies to participant decisions, not to admin force-cancel.
    if actor in ("provider", "client") and now is not None and now - booking.created_at >= EXPIRATION_DELAY:
        raise InvalidState("Booking has expired")

    if booking.status in (CONFIRMED, CANCELLED):
        return booking

    provider_contact = provider_directory.get_provider_contact(booking.provider_id)
    provider_name = provider_contact.get("name") or "La prestataire ou le prestataire"
    salon_address = provider_contact.get("salon_address") or "Adresse à confirmer"
    deposit_percentage = provider_contact.get("deposit_percentage") or 30

    effective_date = booking.proposed_date or booking.desired_date
    effective_price_cents = (
        booking.proposed_price_cents
        if booking.proposed_price_cents is not None
        else booking.estimated_price_cents
    )
    formatted_price = _format_euros(effective_price_cents)

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
                ["La personne cliente se déplace chez toi."]
                if is_salon
                else [f"Adresse de la personne cliente : {client_address}", provider_address_note]
            )
            client_location_lines = (
                [f"Adresse de la prestataire : {salon_address}", client_address_note]
                if is_salon
                else ["Le profil partenaire se déplace jusqu'à toi."]
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
                        *_payment_lines(effective_price_cents, captured=True, deposit_percentage=deposit_percentage),
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
                        *_payment_lines(effective_price_cents, captured=True, deposit_percentage=deposit_percentage),
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
                                *_payment_lines(effective_price_cents, captured=True, deposit_percentage=deposit_percentage),
                                "",
                                "À très vite,",
                                "L'équipe Château Rose",
                            ]
                        ),
                    )
            if operations_email:
                notifier.notify(
                    operations_email,
                    "Acompte débité · rendez-vous confirmé",
                    "\n".join(
                        [
                            "Un rendez-vous vient d'être confirmé et l'acompte a été débité.",
                            f"- ID demande : {booking.id}",
                            f"- Prestataire : {provider_name}",
                            f"- Cliente : {booking.client_contact['name']} ({booking.client_contact['email']})",
                            f"- Date : {effective_date}",
                            f"- Lieu : {location_label}",
                            f"- Tarif total : {formatted_price}",
                            *[
                                line.replace("directement au salon/prestataire", "chez la prestataire")
                                for line in _payment_lines(
                                    effective_price_cents,
                                    captured=True,
                                    deposit_percentage=deposit_percentage,
                                )
                            ],
                        ]
                    ),
                    reply_to=booking.client_contact["email"],
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
                        *_payment_lines(effective_price_cents, captured=False, deposit_percentage=deposit_percentage),
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
                        "La demande a été refusée par la prestataire.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        *_payment_lines(effective_price_cents, captured=False, deposit_percentage=deposit_percentage),
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
                ["La personne cliente se déplace chez toi."]
                if is_salon
                else [f"Adresse de la personne cliente : {client_address}", provider_address_note]
            )
            client_location_lines = (
                [f"Adresse de la prestataire : {salon_address}", client_address_note]
                if is_salon
                else ["Le profil partenaire se déplace jusqu'à toi."]
            )
            notifier.notify(
                booking.provider_id,
                "Rendez-vous confirmé",
                "\n".join(
                    [
                        f"Bonjour {provider_name},",
                        "",
                        "La personne cliente a accepté la proposition.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        *_payment_lines(effective_price_cents, captured=True, deposit_percentage=deposit_percentage),
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
                        *_payment_lines(effective_price_cents, captured=True, deposit_percentage=deposit_percentage),
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
                                *_payment_lines(effective_price_cents, captured=True, deposit_percentage=deposit_percentage),
                                "",
                                "À très vite,",
                                "L'équipe Château Rose",
                            ]
                        ),
                    )
            if operations_email:
                notifier.notify(
                    operations_email,
                    "Acompte débité · rendez-vous confirmé",
                    "\n".join(
                        [
                            "Une proposition a été acceptée et l'acompte a été débité.",
                            f"- ID demande : {booking.id}",
                            f"- Prestataire : {provider_name}",
                            f"- Cliente : {booking.client_contact['name']} ({booking.client_contact['email']})",
                            f"- Date : {effective_date}",
                            f"- Lieu : {location_label}",
                            f"- Tarif total : {formatted_price}",
                            *[
                                line.replace("directement au salon/prestataire", "chez la prestataire")
                                for line in _payment_lines(
                                    effective_price_cents,
                                    captured=True,
                                    deposit_percentage=deposit_percentage,
                                )
                            ],
                        ]
                    ),
                    reply_to=booking.client_contact["email"],
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
                        "La personne cliente a refusé la proposition.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        *_payment_lines(effective_price_cents, captured=False, deposit_percentage=deposit_percentage),
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
                        *_payment_lines(effective_price_cents, captured=False, deposit_percentage=deposit_percentage),
                        "",
                        "Si tu veux, tu peux déposer une nouvelle demande.",
                        "À bientôt,",
                        "L'équipe Château Rose",
                    ]
                ),
            )
        else:
            raise InvalidState("Invalid state for client decision")
    elif actor == "admin":
        if decision == "cancel" and booking.status in (SUBMITTED, PENDING_CLIENT_VALIDATION):
            booking.status = CANCELLED
            payment_gateway.release_auth(booking.payment_auth_id)
            notifier.notify(
                booking.provider_id,
                "Demande annulée",
                "\n".join(
                    [
                        f"Bonjour {provider_name},",
                        "",
                        "La demande a été annulée par l'équipe Château Rose.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        *_payment_lines(effective_price_cents, captured=False, deposit_percentage=deposit_percentage),
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
                        "Ta demande a été annulée par l'équipe Château Rose.",
                        "Récapitulatif :",
                        f"- Date : {effective_date}",
                        f"- Lieu : {location_label}",
                        f"- Tarif : {formatted_price}",
                        "",
                        *_payment_lines(effective_price_cents, captured=False, deposit_percentage=deposit_percentage),
                        "",
                        "Si tu veux, tu peux déposer une nouvelle demande.",
                        "À bientôt,",
                        "L'équipe Château Rose",
                    ]
                ),
            )
        else:
            raise InvalidState("Invalid state for admin decision")
    else:
        raise InvalidState("Unknown actor")

    booking.updated_at = effective_now
    booking_repository.update(booking)
    return booking
