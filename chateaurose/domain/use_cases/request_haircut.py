import uuid
from datetime import timedelta

from chateaurose.domain.entities.booking import BookingRequest

SUBMITTED = "SUBMITTED"


def _generate_id() -> str:
    return f"booking_{uuid.uuid4().hex}"


def execute(
    *,
    provider_id: str,
    service_id: str,
    client_contact: dict,
    location: str,
    desired_date: str,
    hair_length: str,
    meche: str,
    current_hair_picture: str,
    inspiration_pictures: list,
    free_text: str,
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
        ("client_phone", client_contact.get("phone")),
        ("location", location),
        ("desired_date", desired_date),
        ("hair_length", hair_length),
        ("meche", meche),
        ("current_hair_picture", current_hair_picture),
    ]:
        if not value:
            raise ValidationError(f"Missing required field: {field_name}")

    try:
        service = provider_catalog.get_service(provider_id, service_id)
    except KeyError:
        raise ValidationError("Service not offered by provider")
    if not provider_catalog.provider_covers_zone(provider_id, location):
        raise ValidationError("Provider does not cover this zone")

    base_price = service["base_price_cents"]
    length_adj = service.get("hair_length_adjustments", {}).get(hair_length, 0)
    meche_adj = service.get("meche_adjustments", {}).get(meche, 0)
    estimated_price = base_price + length_adj + meche_adj

    booking_id = _generate_id()
    payment_auth_id = payment_gateway.create_auth(
        amount_cents=1000,
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
    )

    booking_repository.add(booking)

    notifier.notify(
        provider_id,
        "Nouvelle demande de coiffure",
        f"{client_contact['name']} veut prendre rendez-vous avec vous.",
    )
    notifier.notify(
        client_contact["phone"],
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
            recipient=client_contact["name"],
            send_at=created_at + timedelta(hours=48),
            subject="Demande expirée",
            body="Votre demande a expiré faute de confirmation.",
        )

    return booking
from chateaurose.domain.exceptions import ValidationError
