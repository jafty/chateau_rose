from datetime import datetime

from booking.models import Provider, ProviderBlockedSlot, Service, Zone
from django.utils import timezone
from chateaurose.domain.exceptions import NotFound

SALON_LOCATION_LABEL = "Salon"


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

    def provider_has_blocked_slot(self, provider_id: str, desired_date: str) -> bool:
        try:
            appointment_at = datetime.fromisoformat(str(desired_date).replace("Z", "+00:00"))
        except ValueError:
            return False

        if timezone.is_naive(appointment_at):
            appointment_at = timezone.make_aware(appointment_at)

        return ProviderBlockedSlot.objects.filter(
            provider_id=provider_id,
            is_active=True,
            starts_at__lte=appointment_at,
            ends_at__gt=appointment_at,
        ).exists()
