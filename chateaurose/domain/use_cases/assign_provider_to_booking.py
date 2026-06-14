from chateaurose.domain.exceptions import InvalidState, NotFound, ValidationError
from chateaurose.domain.services.pricing import estimate_service_price_cents

WAITING_PROVIDER_ASSIGNMENT = "WAITING_PROVIDER_ASSIGNMENT"
AWAITING_ALTERNATIVE_PROVIDER = "AWAITING_ALTERNATIVE_PROVIDER"
SUBMITTED = "SUBMITTED"


def execute(
    *,
    booking_id: str,
    provider_id: str,
    service_id: str,
    booking_repository,
    provider_catalog,
    notifier,
    clock,
    provider_booking_url_base: str | None = None,
    operations_email: str | None = None,
    enforce_service_intent_match: bool = True,
    enforce_pricing_options: bool = False,
):
    booking = booking_repository.get(booking_id)
    if booking.status not in (WAITING_PROVIDER_ASSIGNMENT, AWAITING_ALTERNATIVE_PROVIDER):
        raise InvalidState("Booking is not waiting for provider assignment")

    try:
        service = provider_catalog.get_service(provider_id, service_id)
    except (KeyError, NotFound) as exc:
        raise ValidationError("Service not offered by provider") from exc

    matches_intent = getattr(provider_catalog, "provider_service_matches_intent", None)
    if enforce_service_intent_match and callable(matches_intent):
        if not matches_intent(
            provider_id=provider_id,
            service_id=service_id,
            requested_marketing_service_id=booking.requested_marketing_service_id,
            requested_marketing_sub_service_id=booking.requested_marketing_sub_service_id,
        ):
            raise ValidationError("Provider service is not compatible with requested intent")

    coverage_location = "Salon" if booking.location_preference == "salon" else booking.location
    if coverage_location and coverage_location != "À préciser" and not provider_catalog.provider_covers_zone(provider_id, coverage_location):
        raise ValidationError("Provider does not cover this zone")

    has_blocked_slot = getattr(provider_catalog, "provider_has_blocked_slot", None)
    if callable(has_blocked_slot) and has_blocked_slot(provider_id, booking.desired_date):
        raise ValidationError("Selected slot is unavailable")

    existing_generic_estimate_cents = booking.provider_price_estimate_cents
    should_keep_generic_estimate = (
        booking.booking_kind == "GENERIC"
        and existing_generic_estimate_cents is not None
    )
    if should_keep_generic_estimate:
        price_cents = existing_generic_estimate_cents
        hair_length = booking.hair_length
        general_adjustments = booking.general_adjustments or booking.requested_options or []
    else:
        try:
            price_cents, hair_length, general_adjustments = estimate_service_price_cents(
                service=service,
                hair_length=booking.hair_length,
                general_adjustments=booking.general_adjustments or booking.requested_options or [],
                meche=booking.meche,
                location_preference=booking.location_preference,
            )
        except ValidationError:
            if enforce_pricing_options:
                raise
            price_cents = service["base_price_cents"]
            hair_length = booking.hair_length
            general_adjustments = booking.general_adjustments or booking.requested_options or []

    booking.provider_id = provider_id
    booking.service_id = service_id
    booking.booking_kind = "PROVIDER_SELECTED"
    booking.status = SUBMITTED
    booking.provider_price_estimate_cents = price_cents
    booking.estimated_price_cents = price_cents + booking.chateau_rose_fee_cents
    booking.hair_length = hair_length
    booking.general_adjustments = general_adjustments
    booking.updated_at = clock.now()
    booking_repository.update(booking)

    provider_booking_url = None
    if provider_booking_url_base:
        provider_booking_url = f"{provider_booking_url_base.rstrip('/')}/{booking.id}/"

    provider_lines = [
        "Nouvelle demande attribuée par Château Rose.",
        f"Client·e : {booking.client_contact.get('name')} ({booking.client_contact.get('email')})",
        f"Prestation : {service.get('name')}",
        f"Date souhaitée : {booking.desired_date}",
        f"ID demande : {booking.id}",
    ]
    if provider_booking_url:
        provider_lines.extend(["", "Pour répondre :", provider_booking_url])
    notifier.notify(provider_id, "Nouvelle demande attribuée", "\n".join(provider_lines))
    notifier.notify(
        booking.client_contact["email"],
        "Ta demande a été transmise à une prestataire",
        "\n".join([
            f"Bonjour {booking.client_contact.get('name')},",
            "",
            "Château Rose a transmis ta demande à une prestataire compatible.",
            "Elle va maintenant pouvoir confirmer, refuser ou proposer un ajustement.",
            f"ID demande : {booking.id}",
        ]),
    )
    if operations_email:
        notifier.notify(
            operations_email,
            "Copie attribution demande",
            "\n".join([
                "Une demande a été assignée manuellement.",
                f"ID demande : {booking.id}",
                f"Prestataire : {provider_id}",
                f"Prestation : {service.get('name')}",
            ]),
        )
    return booking
