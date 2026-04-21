from chateaurose.domain.exceptions import ValidationError


def execute(
    *,
    provider_id: str | int,
    service_id: str | int,
    service_name: str,
    client_name: str,
    client_email: str,
    desired_date_iso: str,
    location_preference: str,
    location: str,
    client_address: str,
    hair_length: str,
    general_adjustments: list[str] | None,
    meche: bool,
    free_text: str,
    service_fee_coupon_code: str | None,
    current_hair_picture: str,
    inspiration_pictures: list[str] | None,
) -> dict:
    required = [
        ("provider_id", provider_id),
        ("service_id", service_id),
        ("service_name", service_name),
        ("client_name", client_name),
        ("client_email", client_email),
        ("desired_date_iso", desired_date_iso),
        ("location_preference", location_preference),
        ("location", location),
        ("current_hair_picture", current_hair_picture),
    ]
    for field_name, value in required:
        if value in (None, ""):
            raise ValidationError(f"Missing required field: {field_name}")

    if location_preference not in {"salon", "domicile"}:
        raise ValidationError("Invalid location_preference")

    normalized_adjustments = [item.strip() for item in (general_adjustments or []) if str(item).strip()]
    normalized_inspiration = [item.strip() for item in (inspiration_pictures or []) if str(item).strip()]
    normalized_address = (client_address or "").strip()

    if location_preference == "domicile" and not normalized_address:
        raise ValidationError("Missing required field: client_address")

    return {
        "provider_id": str(provider_id),
        "service_id": str(service_id),
        "service_name": service_name.strip(),
        "client_name": client_name.strip(),
        "client_email": client_email.strip(),
        "desired_date": desired_date_iso.strip(),
        "location_preference": location_preference,
        "location": location.strip(),
        "client_address": normalized_address,
        "hair_length": (hair_length or "").strip(),
        "general_adjustments": normalized_adjustments,
        "meche": bool(meche),
        "free_text": (free_text or "").strip(),
        "service_fee_coupon_code": (service_fee_coupon_code or "").strip().upper(),
        "current_hair_picture": current_hair_picture.strip(),
        "inspiration_pictures": normalized_inspiration,
    }
