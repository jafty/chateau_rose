import uuid
from datetime import timedelta

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import ValidationError
from chateaurose.domain.services.pricing import estimate_service_price_cents

SUBMITTED = "SUBMITTED"
SALON_LOCATION_LABEL = "Salon"


def _format_euros(amount_cents: int) -> str:
    euros = amount_cents / 100
    return f"{euros:.2f}".replace(".", ",") + " €"


def _generate_id() -> str:
    readable = uuid.uuid4().hex[:8].upper()
    return f"BK-{readable}"


def execute(
    *,
    provider_id: str,
    service_id: str,
    client_contact: dict,
    location: str,
    location_preference: str | None,
    client_address: str | None = None,
    desired_date: str,
    hair_length: str,
    general_adjustments: list[str] | None = None,
    meche: bool,
    current_hair_picture: str,
    require_current_hair_picture: bool = True,
    skip_coverage_validation: bool = False,
    inspiration_pictures: list,
    free_text: str,
    payment_auth_id: str | None = None,
    provider_booking_url_base: str | None = None,
    provider_salon_zone: str | None = None,
    booking_repository,
    provider_catalog,
    payment_gateway,
    notifier,
    reminder_gateway,
    clock,
    send_submission_notifications: bool = True,
    operations_email: str | None = None,
):
    required_fields = [
        ("provider_id", provider_id),
        ("service_id", service_id),
        ("client_name", client_contact.get("name")),
        ("client_email", client_contact.get("email")),
        ("location_preference", location_preference),
        ("desired_date", desired_date),
    ]
    if require_current_hair_picture:
        required_fields.append(("current_hair_picture", current_hair_picture))

    for field_name, value in required_fields:
        if not value:
            raise ValidationError(f"Missing required field: {field_name}")
    if meche is None:
        raise ValidationError("Missing required field: meche")

    normalized_location_preference = location_preference
    normalized_location = location
    if normalized_location_preference == "salon":
        if not provider_salon_zone:
            raise ValidationError("Missing required field: provider_salon_zone")
        normalized_location = provider_salon_zone
    else:
        if not normalized_location:
            raise ValidationError("Missing required field: location")
        if not client_address:
            raise ValidationError("Missing required field: client_address")

    try:
        service = provider_catalog.get_service(provider_id, service_id)
    except KeyError:
        raise ValidationError("Service not offered by provider")
    coverage_location = (
        SALON_LOCATION_LABEL
        if normalized_location_preference == "salon"
        else normalized_location
    )
    if not skip_coverage_validation and not provider_catalog.provider_covers_zone(provider_id, coverage_location):
        raise ValidationError("Provider does not cover this zone")

    has_blocked_slot = getattr(provider_catalog, "provider_has_blocked_slot", None)
    if callable(has_blocked_slot) and has_blocked_slot(provider_id, desired_date):
        raise ValidationError("Selected slot is unavailable")

    estimated_price, hair_length, general_adjustments = estimate_service_price_cents(
        service=service,
        hair_length=hair_length,
        general_adjustments=general_adjustments,
        meche=meche,
        location_preference=normalized_location_preference,
    )
    deposit_percentage = service.get("deposit_percentage")
    if deposit_percentage is not None:
        deposit_cents = round(estimated_price * deposit_percentage / 100)
    else:
        deposit_cents = service.get("deposit_cents")
    if deposit_cents is None:
        raise ValidationError("Missing required field: deposit configuration")

    booking_id = _generate_id()
    if not payment_auth_id:
        payment_auth_id = payment_gateway.create_auth(
            amount_cents=deposit_cents,
            currency="EUR",
            reference=booking_id,
        )

    created_at = clock.now()
    booking = BookingRequest(
        id=booking_id,
        provider_id=provider_id,
        service_id=service_id,
        client_contact=client_contact,
        location=normalized_location,
        location_preference=normalized_location_preference,
        desired_date=desired_date,
        hair_length=hair_length,
        general_adjustments=general_adjustments,
        meche=meche,
        current_hair_picture=current_hair_picture,
        inspiration_pictures=inspiration_pictures,
        free_text=free_text,
        estimated_price_cents=estimated_price,
        payment_auth_id=payment_auth_id,
        status=SUBMITTED,
        created_at=created_at,
        updated_at=created_at,
        client_address=client_address,
    )

    booking_repository.add(booking)

    provider_booking_url = None
    if provider_booking_url_base:
        provider_booking_url = f"{provider_booking_url_base.rstrip('/')}/{booking_id}/"

    provider_message_lines = [
        "Bonne nouvelle ! Tu as une nouvelle demande de coiffure.",
        f"Client·e : {client_contact['name']} ({client_contact['email']})",
        f"Prestation : {service['name']}",
        f"Date souhaitée : {desired_date}",
        f"Lieu : {location}",
        f"Longueur : {hair_length}",
        f"Mèches : {'oui' if meche else 'non'}",
        f"ID demande : {booking_id}",
        "",
        "Paiement :",
        f"- Empreinte bancaire validée : {_format_euros(deposit_cents)} (pas encore débités)",
        f"- Débit des frais de réservation uniquement après confirmation : {_format_euros(deposit_cents)}",
        f"- Reste à régler chez la prestataire : {_format_euros(max(estimated_price - deposit_cents, 0))}",
    ]
    if free_text:
        provider_message_lines.append(f"Message : {free_text}")
    if provider_booking_url:
        provider_message_lines.extend(
            [
                "",
                "Pour répondre et proposer un créneau, ouvre la demande :",
                provider_booking_url,
            ]
        )

    client_message_lines = [
        f"Merci {client_contact['name']} ! Ta demande pour {service['name']} est bien envoyée.",
        "On revient vers toi dès que la coiffeuse te propose un créneau.",
        "",
        "Récapitulatif :",
        f"- Prestation : {service['name']}",
        f"- Date souhaitée : {desired_date}",
        f"- Lieu : {location}",
        f"- Longueur : {hair_length}",
        f"- Mèches : {'oui' if meche else 'non'}",
        f"- ID demande : {booking_id}",
        "",
        "Paiement :",
        f"- Empreinte bancaire déjà validée : {_format_euros(deposit_cents)} (pas encore débités)",
        f"- Montant qui sera débité à la confirmation : {_format_euros(deposit_cents)}",
        f"- Reste à régler chez la prestataire : {_format_euros(max(estimated_price - deposit_cents, 0))}",
    ]
    if free_text:
        client_message_lines.append(f"- Ton message : {free_text}")

    if send_submission_notifications:
        notifier.notify(
            provider_id,
            "Nouvelle demande de coiffure",
            "\n".join(provider_message_lines),
        )
        if operations_email:
            notifier.notify(
                operations_email,
                f"Copie demande {booking_id}",
                "\n".join(provider_message_lines),
                reply_to=client_contact["email"],
            )
        notifier.notify(
            client_contact["email"],
            "Demande envoyée",
            "\n".join(client_message_lines),
        )

    if reminder_gateway:
        reminder_gateway.schedule(
            recipient=provider_id,
            send_at=created_at + timedelta(hours=24),
            subject="Rappel: demande en attente",
            body="Tu as une demande en attente de réponse.",
        )
        reminder_gateway.schedule(
            recipient=provider_id,
            send_at=created_at + timedelta(hours=48),
            subject="Demande expirée",
            body="La demande a expiré faute de confirmation.",
        )
        reminder_gateway.schedule(
            recipient=client_contact["email"],
            send_at=created_at + timedelta(hours=48),
            subject="Demande expirée",
            body="Ta demande a expiré faute de confirmation.",
        )

    return booking
