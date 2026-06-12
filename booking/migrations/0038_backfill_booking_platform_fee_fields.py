from django.db import migrations


def _split_provider_price_and_fee(total_cents, service_fee_percentage):
    if not total_cents:
        return 0, 0
    if not service_fee_percentage:
        return total_cents, 0
    estimated_subtotal = round(total_cents * 100 / (100 + service_fee_percentage))
    subtotal_cents = estimated_subtotal
    for candidate in range(max(0, estimated_subtotal - 5), estimated_subtotal + 6):
        candidate_fee = round(candidate * service_fee_percentage / 100)
        if candidate + candidate_fee == total_cents:
            subtotal_cents = candidate
            break
    return subtotal_cents, max(total_cents - subtotal_cents, 0)


def backfill_booking_payment_fields(apps, schema_editor):
    Booking = apps.get_model("booking", "Booking")

    for booking in Booking.objects.select_related("provider").all().iterator():
        update_fields = []

        if not booking.booking_kind:
            booking.booking_kind = "PROVIDER_SELECTED" if booking.provider_id else "GENERIC"
            update_fields.append("booking_kind")

        if not booking.requested_service_label_snapshot and booking.service_id:
            service = getattr(booking, "service", None)
            if service is not None:
                booking.requested_service_label_snapshot = service.name
                update_fields.append("requested_service_label_snapshot")

        provider_price_cents = booking.provider_price_estimate_cents
        service_fee_cents = booking.chateau_rose_fee_cents
        amount_due_now_cents = booking.amount_due_now_cents

        if provider_price_cents is None:
            fee_percentage = 0
            if booking.provider_id and booking.provider is not None:
                fee_percentage = booking.provider.service_fee_percentage or 0
            provider_price_cents, inferred_service_fee_cents = _split_provider_price_and_fee(
                booking.estimated_price_cents or 0,
                fee_percentage,
            )
            booking.provider_price_estimate_cents = provider_price_cents
            update_fields.append("provider_price_estimate_cents")
            if service_fee_cents == 0:
                service_fee_cents = inferred_service_fee_cents
                booking.chateau_rose_fee_cents = service_fee_cents
                update_fields.append("chateau_rose_fee_cents")

        # Existing bookings may already have a Stripe authorization for the legacy
        # reservation fee. Keep amount_due_now aligned with the amount to capture/release
        # instead of silently treating those authorizations as waived.
        if amount_due_now_cents == 0 and booking.payment_auth_id:
            if booking.locked_reservation_fee_cents is not None:
                amount_due_now_cents = booking.locked_reservation_fee_cents
            elif service_fee_cents:
                amount_due_now_cents = service_fee_cents
            else:
                amount_due_now_cents = booking.estimated_price_cents or 0
            booking.amount_due_now_cents = amount_due_now_cents
            update_fields.append("amount_due_now_cents")

        if booking.payment_status == "REQUIRES_PAYMENT":
            if booking.payment_auth_id:
                booking.payment_status = "AUTHORIZED"
            elif amount_due_now_cents == 0:
                booking.payment_status = "WAIVED"
            if booking.payment_status != "REQUIRES_PAYMENT":
                update_fields.append("payment_status")

        if update_fields:
            booking.save(update_fields=sorted(set(update_fields)))


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0037_booking_amount_due_now_cents_booking_booking_kind_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_booking_payment_fields, migrations.RunPython.noop),
    ]
