from datetime import datetime
from typing import TypedDict

from booking.models import Provider, ProviderBlockedSlot, Service, Zone
from django.utils import timezone
from chateaurose.domain.exceptions import NotFound

SALON_LOCATION_LABEL = "Salon"


class BlockedSlotDetails(TypedDict):
    reason: str | None


class DjangoProviderCatalog:
    @staticmethod
    def _normalize_hair_length_adjustments(adjustments):
        if adjustments:
            return adjustments
        return {"standard": 0}

    def get_service(self, provider_id: str, service_id: str):
        try:
            service = Service.objects.get(provider_id=provider_id, id=service_id)
        except Service.DoesNotExist as exc:
            raise NotFound("Service not offered by provider") from exc
        return {
            "id": str(service.id),
            "name": service.name,
            "base_price_cents": service.base_price_cents,
            "hair_length_adjustments": self._normalize_hair_length_adjustments(
                service.hair_length_adjustments
            ),
            "general_adjustments": service.general_adjustments or {},
            "meche_bonus_cents": service.meche_bonus_cents,
            "at_home_bonus_cents": service.at_home_bonus_cents,
            "deposit_cents": service.provider.deposit_cents,
            "deposit_percentage": service.provider.deposit_percentage,
            "service_fee_percentage": service.provider.service_fee_percentage,
            "marketing_service_id": str(service.marketing_service_id) if service.marketing_service_id else None,
            "marketing_sub_service_ids": [str(item) for item in service.marketing_sub_services.values_list("id", flat=True)],
        }

    def provider_covers_zone(self, provider_id: str, zone_name: str) -> bool:
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            return False

        if provider.location_mode == Provider.LOCATION_MODE_SALON_ONLY:
            return zone_name == SALON_LOCATION_LABEL

        if provider.location_mode == Provider.LOCATION_MODE_HYBRID and zone_name == SALON_LOCATION_LABEL:
            return True

        return Zone.objects.filter(providers__id=provider_id, name=zone_name).exists()

    def get_blocked_slot_details(self, provider_id: str, desired_date: str) -> BlockedSlotDetails | None:
        try:
            appointment_at = datetime.fromisoformat(str(desired_date).replace("Z", "+00:00"))
        except ValueError:
            return None

        if timezone.is_naive(appointment_at):
            appointment_at = timezone.make_aware(appointment_at)

        punctual_slot = ProviderBlockedSlot.objects.filter(
            provider_id=provider_id,
            is_active=True,
            is_recurring=False,
            starts_at__lte=appointment_at,
            ends_at__gt=appointment_at,
        ).order_by("starts_at").first()
        if punctual_slot:
            return {"reason": punctual_slot.reason or None}

        local_appointment = timezone.localtime(appointment_at)
        appointment_date = local_appointment.date()
        appointment_time = local_appointment.time()

        recurring_slots = ProviderBlockedSlot.objects.filter(
            provider_id=provider_id,
            is_active=True,
            is_recurring=True,
        )

        for blocked_slot in recurring_slots:
            if blocked_slot.matches_recurrence(appointment_date, appointment_time):
                return {"reason": blocked_slot.reason or None}
        return None

    def provider_has_blocked_slot(self, provider_id: str, desired_date: str) -> bool:
        return self.get_blocked_slot_details(provider_id, desired_date) is not None

    def provider_service_matches_intent(
        self,
        *,
        provider_id: str,
        service_id: str,
        requested_marketing_service_id: str | None = None,
        requested_marketing_sub_service_id: str | None = None,
    ) -> bool:
        try:
            service = Service.objects.get(id=service_id, provider_id=provider_id)
        except Service.DoesNotExist:
            return False

        if requested_marketing_sub_service_id:
            if service.marketing_sub_services.filter(id=requested_marketing_sub_service_id).exists():
                return True
            return service.provider.marketing_sub_services.filter(id=requested_marketing_sub_service_id).exists()

        if requested_marketing_service_id:
            if service.marketing_service_id and str(service.marketing_service_id) == str(requested_marketing_service_id):
                return True
            return service.provider.marketing_services.filter(id=requested_marketing_service_id).exists()

        return True
