from chateaurose.domain.exceptions import ValidationError


STANDARD_ADJUSTMENT_KEY = "standard"
SALON_LOCATION_PREFERENCE = "salon"


def estimate_service_price_cents(
    *,
    service: dict,
    hair_length: str | None,
    general_adjustment: str | None,
    meche: bool,
    location_preference: str | None,
) -> tuple[int, str, str | None]:
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

    raw_general_adjustments = service.get("general_adjustments") or {}
    if raw_general_adjustments:
        general_adjustments = raw_general_adjustments
        default_general_adjustment = None
    else:
        general_adjustments = {STANDARD_ADJUSTMENT_KEY: 0}
        default_general_adjustment = STANDARD_ADJUSTMENT_KEY

    normalized_general_adjustment = general_adjustment
    general_adj_value = 0
    if normalized_general_adjustment:
        if normalized_general_adjustment not in general_adjustments:
            raise ValidationError("General adjustment is not supported for this service")
        general_adj_value = general_adjustments[normalized_general_adjustment]
    elif default_general_adjustment:
        normalized_general_adjustment = default_general_adjustment
        general_adj_value = general_adjustments[normalized_general_adjustment]

    meche_bonus = service.get("meche_bonus_cents", 0) if meche else 0
    domicile_bonus = (
        service.get("at_home_bonus_cents", 0)
        if location_preference != SALON_LOCATION_PREFERENCE
        else 0
    )

    estimated_price = base_price + length_adj + general_adj_value + meche_bonus + domicile_bonus
    return estimated_price, normalized_hair_length, normalized_general_adjustment
