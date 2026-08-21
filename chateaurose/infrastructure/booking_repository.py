from booking.models import Booking, Provider, Service
from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import NotFound


class DjangoBookingRepository:
    def add(self, booking: BookingRequest):
        provider_obj = (
            Provider.objects.get(id=booking.provider_id)
            if booking.provider_id
            else None
        )
        service_obj = None
        if booking.service_id:
            service_queryset = Service.objects.filter(id=booking.service_id)
            if provider_obj is not None:
                service_queryset = service_queryset.filter(provider=provider_obj)
            service_obj = service_queryset.get()

        updated_at = getattr(booking, "updated_at", None) or booking.created_at

        Booking.objects.create(
            booking_id=booking.id,
            booking_kind=booking.booking_kind,
            provider=provider_obj,
            service=service_obj,
            requested_marketing_service_id=booking.requested_marketing_service_id,
            requested_marketing_sub_service_id=booking.requested_marketing_sub_service_id,
            requested_service_label_snapshot=booking.requested_service_label_snapshot
            or "",
            requested_options=booking.requested_options or [],
            client_name=booking.client_contact.get("name", ""),
            client_email=booking.client_contact.get("email", ""),
            client_phone=booking.client_contact.get("phone", ""),
            location=booking.location,
            location_preference=booking.location_preference or "",
            client_address=booking.client_address or "",
            desired_date=booking.desired_date,
            hair_length=booking.hair_length,
            general_adjustments=booking.general_adjustments or [],
            meche=booking.meche,
            current_hair_picture=booking.current_hair_picture,
            inspiration_pictures=booking.inspiration_pictures,
            free_text=booking.free_text,
            estimated_price_cents=booking.estimated_price_cents,
            provider_price_estimate_cents=booking.provider_price_estimate_cents,
            chateau_rose_fee_cents=booking.chateau_rose_fee_cents,
            amount_due_now_cents=booking.amount_due_now_cents,
            payment_status=booking.payment_status,
            payment_auth_id=booking.payment_auth_id or "",
            status=booking.status,
            alternative_requested_at=booking.alternative_requested_at,
            proposed_price_cents=booking.proposed_price_cents,
            proposed_date=booking.proposed_date,
            created_at=booking.created_at,
            updated_at=updated_at,
            state_entered_at=booking.state_entered_at or updated_at,
            initial_provider_deadline_at=booking.initial_provider_deadline_at,
            process_expires_at=booking.process_expires_at,
        )
        return booking

    def get(self, booking_id: str) -> BookingRequest:
        try:
            obj = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist as exc:
            raise NotFound(f"Booking {booking_id} not found") from exc
        return self._to_domain(obj)

    def update(self, booking: BookingRequest):
        provider_obj = (
            Provider.objects.get(id=booking.provider_id)
            if booking.provider_id
            else None
        )
        service_obj = None
        if booking.service_id:
            service_queryset = Service.objects.filter(id=booking.service_id)
            if provider_obj is not None:
                service_queryset = service_queryset.filter(provider=provider_obj)
            service_obj = service_queryset.get()

        updated_at = getattr(booking, "updated_at", None) or booking.created_at

        count = Booking.objects.filter(booking_id=booking.id).update(
            booking_kind=booking.booking_kind,
            provider=provider_obj,
            service=service_obj,
            requested_marketing_service_id=booking.requested_marketing_service_id,
            requested_marketing_sub_service_id=booking.requested_marketing_sub_service_id,
            requested_service_label_snapshot=booking.requested_service_label_snapshot
            or "",
            requested_options=booking.requested_options or [],
            client_name=booking.client_contact.get("name", ""),
            client_email=booking.client_contact.get("email", ""),
            client_phone=booking.client_contact.get("phone", ""),
            location=booking.location,
            location_preference=booking.location_preference or "",
            client_address=booking.client_address or "",
            desired_date=booking.desired_date,
            hair_length=booking.hair_length,
            general_adjustments=booking.general_adjustments or [],
            meche=booking.meche,
            current_hair_picture=booking.current_hair_picture,
            inspiration_pictures=booking.inspiration_pictures,
            free_text=booking.free_text,
            estimated_price_cents=booking.estimated_price_cents,
            provider_price_estimate_cents=booking.provider_price_estimate_cents,
            chateau_rose_fee_cents=booking.chateau_rose_fee_cents,
            amount_due_now_cents=booking.amount_due_now_cents,
            payment_status=booking.payment_status,
            payment_auth_id=booking.payment_auth_id or "",
            status=booking.status,
            alternative_requested_at=booking.alternative_requested_at,
            proposed_price_cents=booking.proposed_price_cents,
            proposed_date=booking.proposed_date,
            created_at=booking.created_at,
            updated_at=updated_at,
            state_entered_at=booking.state_entered_at or updated_at,
            initial_provider_deadline_at=booking.initial_provider_deadline_at,
            process_expires_at=booking.process_expires_at,
        )
        if not count:
            raise NotFound(f"Booking {booking.id} not found")
        return booking

    def _to_domain(self, obj: Booking) -> BookingRequest:
        return BookingRequest(
            id=obj.booking_id,
            booking_kind=obj.booking_kind,
            provider_id=str(obj.provider_id) if obj.provider_id else None,
            service_id=str(obj.service_id) if obj.service_id else None,
            requested_marketing_service_id=(
                str(obj.requested_marketing_service_id)
                if obj.requested_marketing_service_id
                else None
            ),
            requested_marketing_sub_service_id=(
                str(obj.requested_marketing_sub_service_id)
                if obj.requested_marketing_sub_service_id
                else None
            ),
            requested_service_label_snapshot=obj.requested_service_label_snapshot or "",
            requested_options=obj.requested_options or [],
            client_contact={
                "name": obj.client_name,
                "email": obj.client_email,
                "phone": obj.client_phone,
            },
            location=obj.location,
            location_preference=obj.location_preference or None,
            desired_date=obj.desired_date,
            hair_length=obj.hair_length,
            general_adjustments=obj.general_adjustments or [],
            meche=obj.meche,
            current_hair_picture=obj.current_hair_picture,
            inspiration_pictures=obj.inspiration_pictures,
            free_text=obj.free_text,
            estimated_price_cents=obj.estimated_price_cents,
            provider_price_estimate_cents=obj.provider_price_estimate_cents,
            chateau_rose_fee_cents=obj.chateau_rose_fee_cents,
            amount_due_now_cents=obj.amount_due_now_cents,
            payment_status=obj.payment_status,
            payment_auth_id=obj.payment_auth_id,
            status=obj.status,
            created_at=obj.created_at,
            alternative_requested_at=obj.alternative_requested_at,
            proposed_price_cents=obj.proposed_price_cents,
            proposed_date=obj.proposed_date,
            updated_at=obj.updated_at,
            state_entered_at=obj.state_entered_at,
            client_address=obj.client_address or None,
            initial_provider_deadline_at=obj.initial_provider_deadline_at,
            process_expires_at=obj.process_expires_at,
        )
