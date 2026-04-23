from chateaurose.domain.exceptions import ValidationError


STANDARD_ADJUSTMENT_KEY = "standard"
SALON_LOCATION_PREFERENCE = "salon"


def estimate_service_price_cents(
    *,
    service: dict,
    hair_length: str | None,
    general_adjustments: list[str] | None,
    meche: bool,
    location_preference: str | None,
) -> tuple[int, str, list[str]]:
    base_price = service["base_price_cents"]

    length_adjustments = service.get("hair_length_adjustments") or {STANDARD_ADJUSTMENT_KEY: 0}
    normalized_hair_length = hair_length
    if not normalized_hair_length:
        if len(length_adjustments) == 1:
            normalized_hair_length = next(iter(length_adjustments))
        else:
            raise ValidationError("Missing required field: hair_length")
    if normalized_hair_length not in length_adjustments:
        raise ValidationError("Hair length is not supported for this service")
    length_adj = length_adjustments[normalized_hair_length]

    selectable_general_adjustments = service.get("general_adjustments") or {}
    if general_adjustments is None:
        raw_general_adjustments = []
    elif isinstance(general_adjustments, (list, tuple)):
        raw_general_adjustments = list(general_adjustments)
    else:
        raise ValidationError("General adjustments must be a list")

    normalized_general_adjustments = [
        str(item).strip() for item in raw_general_adjustments if str(item).strip()
    ]

    unknown_adjustments = [
        item for item in normalized_general_adjustments if item not in selectable_general_adjustments
    ]
    if unknown_adjustments:
        raise ValidationError("General adjustment is not supported for this service")

    general_adj_value = sum(
        selectable_general_adjustments[item] for item in normalized_general_adjustments
    )

    meche_bonus = service.get("meche_bonus_cents", 0) if meche else 0
    domicile_bonus = (
        service.get("at_home_bonus_cents", 0)
        if location_preference != SALON_LOCATION_PREFERENCE
        else 0
    )

    estimated_price = base_price + length_adj + general_adj_value + meche_bonus + domicile_bonus
    return estimated_price, normalized_hair_length, normalized_general_adjustments


def compute_checkout_amounts_cents(
    *,
    subtotal_cents: int,
    deposit_percentage: int,
    service_fee_percentage: int,
    waive_service_fee: bool = False,
) -> dict:
    deposit_cents = round(subtotal_cents * deposit_percentage / 100)
    service_fee_cents = 0 if waive_service_fee else round(subtotal_cents * service_fee_percentage / 100)
    total_cents = subtotal_cents + service_fee_cents
    reservation_fee_cents = deposit_cents + service_fee_cents
    remaining_cents = max(total_cents - reservation_fee_cents, 0)
    return {
        "subtotal_cents": subtotal_cents,
        "deposit_cents": deposit_cents,
        "service_fee_cents": service_fee_cents,
        "total_cents": total_cents,
        "reservation_fee_cents": reservation_fee_cents,
        "remaining_cents": remaining_cents,
    }


def ceil_price_for_display_cents(amount_cents: int) -> int:
    if amount_cents <= 0:
        return 0
    euros, cents = divmod(amount_cents, 100)
    return (euros + (1 if cents else 0)) * 100
