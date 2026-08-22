from chateaurose.domain.use_cases import create_booking_request

SUBMITTED = create_booking_request.SUBMITTED
SALON_LOCATION_LABEL = create_booking_request.SALON_LOCATION_LABEL


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
    type_adjustment: str = "standard",
    general_adjustments: list[str] | None = None,
    meche: bool,
    current_hair_picture: str = "",
    skip_coverage_validation: bool = False,
    inspiration_pictures: list | None = None,
    free_text: str = "",
    service_fee_coupon_code: str | None = None,
    waive_service_fee: bool = False,
    payment_auth_id: str | None = None,
    provider_booking_url_base: str | None = None,
    provider_salon_zone: str | None = None,
    booking_repository=None,
    provider_catalog=None,
    payment_gateway=None,
    notifier=None,
    reminder_gateway=None,
    clock=None,
    send_submission_notifications: bool = True,
    operations_email: str | None = None,
):
    # Legacy provider-selected entry point kept for existing views/tests.
    # New payment semantics: amount due online is only Château Rose's service fee;
    # the hairstyle price is paid directly to the provider on appointment day.
    from chateaurose.domain.exceptions import ValidationError

    if meche is None:
        raise ValidationError("Missing required field: meche")
    if location_preference == "salon" and not provider_salon_zone:
        raise ValidationError("Missing required field: provider_salon_zone")
    if location_preference != "salon":
        if not location:
            raise ValidationError("Missing required field: location")

    return create_booking_request.execute(
        provider_id=provider_id,
        service_id=service_id,
        client_contact=client_contact,
        location=location,
        location_preference=location_preference,
        client_address=client_address,
        desired_date=desired_date,
        hair_length=hair_length,
        type_adjustment=type_adjustment,
        general_adjustments=general_adjustments,
        requested_options=general_adjustments,
        meche=meche,
        current_hair_picture=current_hair_picture,
        inspiration_pictures=inspiration_pictures or [],
        free_text=free_text,
        service_fee_coupon_code=service_fee_coupon_code,
        waive_service_fee=waive_service_fee,
        payment_auth_id=payment_auth_id,
        provider_booking_url_base=provider_booking_url_base,
        provider_salon_zone=provider_salon_zone,
        skip_coverage_validation=skip_coverage_validation,
        booking_repository=booking_repository,
        provider_catalog=provider_catalog,
        payment_gateway=payment_gateway,
        notifier=notifier,
        reminder_gateway=reminder_gateway,
        clock=clock,
        send_submission_notifications=send_submission_notifications,
        operations_email=operations_email,
    )
