import uuid

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import NotFound, ValidationError
from chateaurose.domain.services.pricing import (
    compute_service_fee_only_amounts_cents,
    estimate_service_price_cents,
)

SUBMITTED = "SUBMITTED"
WAITING_PROVIDER_ASSIGNMENT = "WAITING_PROVIDER_ASSIGNMENT"
BOOKING_KIND_PROVIDER_SELECTED = "PROVIDER_SELECTED"
BOOKING_KIND_GENERIC = "GENERIC"
PAYMENT_STATUS_AUTHORIZED = "AUTHORIZED"
PAYMENT_STATUS_WAIVED = "WAIVED"
SALON_LOCATION_LABEL = "Salon"


def _generate_id() -> str:
    return f"BK-{uuid.uuid4().hex[:8].upper()}"


def _format_euros(amount_cents: int) -> str:
    return f"{amount_cents / 100:.2f}".replace(".", ",") + " €"


def _build_client_details_request_lines(client_name: str) -> list[str]:
    return [
        f"Bonjour {client_name},",
        "",
        "Pour préparer au mieux ta coupe, tu peux répondre directement à cet email avec les éléments utiles pour la prestataire.",
        "Si c’est pertinent, ajoute une photo récente de tes cheveux, une photo d’inspiration de la coupe souhaitée et toute précision importante (longueur, volume, contraintes, habitudes, questions).",
        "Ces informations nous aideront à valider que la prestation prévue correspond bien à tes attentes.",
        "",
        "À très vite,",
        "Château Rose",
    ]


def _client_details_reply_to(provider_id: str, operations_email: str | None):
    recipients = [provider_id]
    if operations_email:
        recipients.append(operations_email)
    return recipients


def _normalize_list(values) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple)):
        raise ValidationError("Requested options must be a list")
    return [str(item).strip() for item in values if str(item).strip()]


def execute(
    *,
    client_contact: dict,
    desired_date: str,
    location_preference: str | None,
    location: str = "",
    client_address: str | None = None,
    hair_length: str = "",
    requested_options: list[str] | None = None,
    general_adjustments: list[str] | None = None,
    meche: bool = False,
    current_hair_picture: str = "",
    inspiration_pictures: list | None = None,
    free_text: str = "",
    provider_id: str | None = None,
    service_id: str | None = None,
    requested_marketing_service_id: str | None = None,
    requested_marketing_sub_service_id: str | None = None,
    requested_service_label_snapshot: str = "",
    chateau_rose_fee_cents: int | None = None,
    generic_provider_price_estimate_cents: int | None = None,
    service_fee_coupon_code: str | None = None,
    waive_service_fee: bool = False,
    payment_auth_id: str | None = None,
    provider_booking_url_base: str | None = None,
    skip_coverage_validation: bool = False,
    provider_salon_zone: str | None = None,
    booking_repository,
    provider_catalog,
    payment_gateway,
    notifier,
    reminder_gateway=None,
    clock,
    send_submission_notifications: bool = True,
    operations_email: str | None = None,
):
    required_fields = [
        ("client_name", client_contact.get("name")),
        ("client_email", client_contact.get("email")),
        ("desired_date", desired_date),
        ("location_preference", location_preference),
    ]
    for field_name, value in required_fields:
        if not value:
            raise ValidationError(f"Missing required field: {field_name}")

    if provider_id and not service_id:
        raise ValidationError("Missing required field: service_id")
    if service_id and not provider_id:
        raise ValidationError("Missing required field: provider_id")
    if not provider_id and not (requested_marketing_service_id or requested_marketing_sub_service_id or requested_service_label_snapshot):
        raise ValidationError("Missing required field: requested service intent")

    normalized_options = _normalize_list(requested_options if requested_options is not None else general_adjustments)
    normalized_adjustments = _normalize_list(general_adjustments if general_adjustments is not None else requested_options)
    normalized_location_preference = location_preference
    normalized_location = location or ""
    if normalized_location_preference == "salon":
        normalized_location = provider_salon_zone or normalized_location or SALON_LOCATION_LABEL
    elif not normalized_location:
        normalized_location = "À préciser"

    provider_price_estimate_cents = generic_provider_price_estimate_cents
    amount_due_now_cents = chateau_rose_fee_cents
    service_name = requested_service_label_snapshot or "prestation demandée"

    if provider_id and service_id:
        try:
            service = provider_catalog.get_service(provider_id, service_id)
        except (KeyError, NotFound) as exc:
            raise ValidationError("Service not offered by provider") from exc

        coverage_location = SALON_LOCATION_LABEL if normalized_location_preference == "salon" else normalized_location
        if (
            not skip_coverage_validation
            and coverage_location != "À préciser"
            and not provider_catalog.provider_covers_zone(provider_id, coverage_location)
        ):
            raise ValidationError("Provider does not cover this zone")

        has_blocked_slot = getattr(provider_catalog, "provider_has_blocked_slot", None)
        if callable(has_blocked_slot) and has_blocked_slot(provider_id, desired_date):
            raise ValidationError("Selected slot is unavailable")

        provider_price_estimate_cents, hair_length, normalized_adjustments = estimate_service_price_cents(
            service=service,
            hair_length=hair_length,
            general_adjustments=normalized_adjustments,
            meche=meche,
            location_preference=normalized_location_preference,
        )
        service_name = service.get("name") or service_name
        amounts = compute_service_fee_only_amounts_cents(
            subtotal_cents=provider_price_estimate_cents,
            service_fee_percentage=service.get("service_fee_percentage", 0),
            waive_service_fee=bool(service.get("waive_service_fee")) or waive_service_fee,
        )
        amount_due_now_cents = amounts["amount_due_now_cents"]

    if amount_due_now_cents is None:
        raise ValidationError("Missing required field: chateau_rose_fee_cents")

    booking_id = _generate_id()
    if amount_due_now_cents > 0:
        if not payment_auth_id:
            payment_auth_id = payment_gateway.create_auth(
                amount_cents=amount_due_now_cents,
                currency="EUR",
                reference=booking_id,
            )
        payment_status = PAYMENT_STATUS_AUTHORIZED
    else:
        payment_auth_id = payment_auth_id or ""
        payment_status = PAYMENT_STATUS_WAIVED

    created_at = clock.now()
    booking = BookingRequest(
        id=booking_id,
        booking_kind=BOOKING_KIND_PROVIDER_SELECTED if provider_id else BOOKING_KIND_GENERIC,
        provider_id=provider_id,
        service_id=service_id,
        requested_marketing_service_id=requested_marketing_service_id,
        requested_marketing_sub_service_id=requested_marketing_sub_service_id,
        requested_service_label_snapshot=requested_service_label_snapshot or service_name,
        requested_options=normalized_options,
        client_contact=client_contact,
        location=normalized_location,
        location_preference=normalized_location_preference,
        desired_date=desired_date,
        hair_length=hair_length,
        general_adjustments=normalized_adjustments,
        meche=meche,
        current_hair_picture=current_hair_picture,
        inspiration_pictures=inspiration_pictures or [],
        free_text=free_text,
        estimated_price_cents=(provider_price_estimate_cents or 0) + amount_due_now_cents,
        provider_price_estimate_cents=provider_price_estimate_cents,
        chateau_rose_fee_cents=amount_due_now_cents,
        amount_due_now_cents=amount_due_now_cents,
        payment_status=payment_status,
        payment_auth_id=payment_auth_id,
        status=SUBMITTED if provider_id else WAITING_PROVIDER_ASSIGNMENT,
        created_at=created_at,
        updated_at=created_at,
        client_address=client_address,
    )
    booking_repository.add(booking)

    if send_submission_notifications:
        if provider_id:
            provider_booking_url = None
            if provider_booking_url_base:
                provider_booking_url = f"{provider_booking_url_base.rstrip('/')}/{booking_id}/"
            provider_lines = [
                "Bonne nouvelle ! Tu as une nouvelle demande de coiffure.",
                f"Client·e : {client_contact['name']} ({client_contact['email']})",
                f"Prestation : {service_name}",
                f"Date souhaitée : {desired_date}",
                f"Lieu : {normalized_location}",
                f"ID demande : {booking_id}",
                "",
                "Paiement Château Rose :",
                f"- Frais de service : {_format_euros(amount_due_now_cents)}",
                "- La prestation coiffure sera réglée directement le jour J.",
            ]
            if provider_booking_url:
                provider_lines.extend(["", "Pour répondre :", provider_booking_url])
            notifier.notify(provider_id, "Nouvelle demande de coiffure", "\n".join(provider_lines))
            if operations_email:
                operations_lines = [
                    "Copie Château Rose d'une nouvelle demande envoyée à une prestataire.",
                    f"- ID demande : {booking_id}",
                    f"- Cliente : {client_contact['name']} ({client_contact['email']})",
                    f"- Téléphone : {client_contact.get('phone') or 'Non communiqué'}",
                    f"- Prestataire : {provider_id}",
                    f"- Prestation : {service_name}",
                    f"- Date souhaitée : {desired_date}",
                    f"- Lieu : {normalized_location}",
                    f"- Frais Château Rose : {_format_euros(amount_due_now_cents)}",
                    f"- Statut paiement : {payment_status}",
                ]
                if provider_booking_url:
                    operations_lines.extend(["", "Lien prestataire :", provider_booking_url])
                notifier.notify(
                    operations_email,
                    f"Copie nouvelle demande · {booking_id}",
                    "\n".join(operations_lines),
                    reply_to=client_contact["email"],
                )
        elif operations_email:
            notifier.notify(
                operations_email,
                f"Nouvelle demande générique · {booking_id}",
                "\n".join([
                    "Une cliente demande à Château Rose de trouver une prestataire compatible.",
                    f"- ID demande : {booking_id}",
                    f"- Cliente : {client_contact['name']} ({client_contact['email']})",
                    f"- Téléphone : {client_contact.get('phone') or 'Non communiqué'}",
                    f"- Prestation : {requested_service_label_snapshot or requested_marketing_sub_service_id or requested_marketing_service_id}",
                    f"- Date souhaitée : {desired_date}",
                    f"- Options / longueur : {', '.join(normalized_options) or hair_length or 'Non précisées'}",
                    f"- Frais Château Rose : {_format_euros(amount_due_now_cents)}",
                    f"- Statut paiement : {payment_status}",
                    "Action : assigner manuellement une prestataire compatible.",
                ]),
                reply_to=client_contact["email"],
            )

        client_lines = [
            f"Merci {client_contact['name']} ! Ta demande est bien enregistrée.",
            "Château Rose a reçu ta demande. Aucune prestataire n'est encore assignée : nous recherchons une prestataire compatible." if not provider_id else "La prestataire va maintenant valider la demande.",
            "",
            "Récapitulatif :",
            f"- Prestation : {service_name}",
            f"- Date souhaitée : {desired_date}",
            f"- Lieu : {normalized_location}",
            f"- ID demande : {booking_id}",
            "",
            "Paiement :",
            f"- Frais Château Rose : {_format_euros(amount_due_now_cents)}",
            "- La prestation coiffure sera réglée directement à la prestataire le jour du rendez-vous.",
        ]
        if not provider_id:
            client_lines.extend([
                "",
                "Château Rose pourra te demander l'adresse exacte, des photos ou des détails complémentaires si nécessaire.",
            ])
        notifier.notify(client_contact["email"], "Demande enregistrée", "\n".join(client_lines))

        if provider_id:
            notifier.notify(
                client_contact["email"],
                "Quelques infos avant de valider ton RDV",
                "\n".join(_build_client_details_request_lines(client_contact["name"])),
                reply_to=_client_details_reply_to(provider_id, operations_email),
            )

    return booking
