import uuid
from datetime import timedelta

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import ValidationError

SUBMITTED = "SUBMITTED"


def _generate_id() -> str:
    readable = uuid.uuid4().hex[:8].upper()
    return f"BK-{readable}"


def execute(
    *,
    provider_id: str,
    service_id: str,
    client_contact: dict,
    location: str,
    desired_date: str,
    hair_length: str,
    meche: bool,
    current_hair_picture: str,
    inspiration_pictures: list,
    free_text: str,
    payment_auth_id: str | None = None,
    booking_repository,
    provider_catalog,
    payment_gateway,
    notifier,
    reminder_gateway,
    clock,
):
    for field_name, value in [
        ("provider_id", provider_id),
        ("service_id", service_id),
        ("client_name", client_contact.get("name")),
        ("client_email", client_contact.get("email")),
        ("location", location),
        ("desired_date", desired_date),
        ("hair_length", hair_length),
        ("current_hair_picture", current_hair_picture),
    ]:
        if not value:
            raise ValidationError(f"Missing required field: {field_name}")
    if meche is None:
        raise ValidationError("Missing required field: meche")

    try:
        service = provider_catalog.get_service(provider_id, service_id)
    except KeyError:
        raise ValidationError("Service not offered by provider")
    if not provider_catalog.provider_covers_zone(provider_id, location):
        raise ValidationError("Provider does not cover this zone")

    base_price = service["base_price_cents"]
    length_adjustments = service.get("hair_length_adjustments", {})
    if hair_length not in length_adjustments:
        raise ValidationError("Hair length is not supported for this service")
    length_adj = length_adjustments[hair_length]
    meche_bonus = service.get("meche_bonus_cents", 0) if meche else 0
    estimated_price = base_price + length_adj + meche_bonus

    booking_id = _generate_id()
    if not payment_auth_id:
        payment_auth_id = payment_gateway.create_auth(
            amount_cents=estimated_price,
            currency="EUR",
            reference=booking_id,
        )

    created_at = clock.now()
    booking = BookingRequest(
        id=booking_id,
        provider_id=provider_id,
        service_id=service_id,
        client_contact=client_contact,
        location=location,
        desired_date=desired_date,
        hair_length=hair_length,
        meche=meche,
        current_hair_picture=current_hair_picture,
        inspiration_pictures=inspiration_pictures,
        free_text=free_text,
        estimated_price_cents=estimated_price,
        payment_auth_id=payment_auth_id,
        status=SUBMITTED,
        created_at=created_at,
        updated_at=created_at,
    )

    booking_repository.add(booking)

    notifier.notify(
        provider_id,
        "Nouvelle demande de coiffure",
        f"{client_contact['name']} veut prendre rendez-vous avec vous.",
    )
    notifier.notify(
        client_contact["email"],
        "Demande envoyée",
        f"{provider_id} a bien reçu votre demande. Vous recevrez un message lorsque le rendez-vous sera confirmé.",
    )

    if reminder_gateway:
        reminder_gateway.schedule(
            recipient=provider_id,
            send_at=created_at + timedelta(hours=24),
            subject="Rappel: demande en attente",
            body="Vous avez une demande en attente de réponse.",
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
            body="Votre demande a expiré faute de confirmation.",
        )

    return booking
