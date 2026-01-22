from booking.models import Booking, Provider, Service
from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import NotFound


class DjangoBookingRepository:
    def add(self, booking: BookingRequest):
        provider_obj = Provider.objects.get(id=booking.provider_id)
        service_obj = Service.objects.get(id=booking.service_id, provider=provider_obj)

        updated_at = getattr(booking, "updated_at", None) or booking.created_at

        Booking.objects.create(
            booking_id=booking.id,
            provider=provider_obj,
            service=service_obj,
            client_name=booking.client_contact["name"],
            client_email=booking.client_contact["email"],
            location=booking.location,
            location_preference=booking.location_preference or "",
            client_address=booking.client_address or "",
            desired_date=booking.desired_date,
            hair_length=booking.hair_length,
            meche=booking.meche,
            current_hair_picture=booking.current_hair_picture,
            inspiration_pictures=booking.inspiration_pictures,
            free_text=booking.free_text,
            estimated_price_cents=booking.estimated_price_cents,
            payment_auth_id=booking.payment_auth_id,
            status=booking.status,
            proposed_price_cents=booking.proposed_price_cents,
            proposed_date=booking.proposed_date,
            created_at=booking.created_at,
            updated_at=updated_at,
        )
        return booking

    def get(self, booking_id: str) -> BookingRequest:
        try:
            obj = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist as exc:
            raise NotFound(f"Booking {booking_id} not found") from exc
        return self._to_domain(obj)

    def update(self, booking: BookingRequest):
        provider_obj = Provider.objects.get(id=booking.provider_id)
        service_obj = Service.objects.get(id=booking.service_id, provider=provider_obj)

        updated_at = getattr(booking, "updated_at", None) or booking.created_at

        count = Booking.objects.filter(booking_id=booking.id).update(
            provider=provider_obj,
            service=service_obj,
            client_name=booking.client_contact["name"],
            client_email=booking.client_contact["email"],
            location=booking.location,
            location_preference=booking.location_preference or "",
            client_address=booking.client_address or "",
            desired_date=booking.desired_date,
            hair_length=booking.hair_length,
            meche=booking.meche,
            current_hair_picture=booking.current_hair_picture,
            inspiration_pictures=booking.inspiration_pictures,
            free_text=booking.free_text,
            estimated_price_cents=booking.estimated_price_cents,
            payment_auth_id=booking.payment_auth_id,
            status=booking.status,
            proposed_price_cents=booking.proposed_price_cents,
            proposed_date=booking.proposed_date,
            created_at=booking.created_at,
            updated_at=updated_at,
        )
        if not count:
            raise NotFound(f"Booking {booking.id} not found")
        return booking

    def _to_domain(self, obj: Booking) -> BookingRequest:
        return BookingRequest(
            id=obj.booking_id,
            provider_id=obj.provider_id,
            service_id=obj.service_id,
            client_contact={"name": obj.client_name, "email": obj.client_email},
            location=obj.location,
            location_preference=obj.location_preference or None,
            desired_date=obj.desired_date,
            hair_length=obj.hair_length,
            meche=obj.meche,
            current_hair_picture=obj.current_hair_picture,
            inspiration_pictures=obj.inspiration_pictures,
            free_text=obj.free_text,
            estimated_price_cents=obj.estimated_price_cents,
            payment_auth_id=obj.payment_auth_id,
            status=obj.status,
            created_at=obj.created_at,
            proposed_price_cents=obj.proposed_price_cents,
            proposed_date=obj.proposed_date,
            updated_at=obj.updated_at,
            client_address=obj.client_address or None,
        )
