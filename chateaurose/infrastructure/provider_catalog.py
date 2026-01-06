from booking.models import Provider, Service, Zone
from chateaurose.domain.exceptions import NotFound

SALON_LOCATION_LABEL = "Salon"


class DjangoProviderCatalog:
    def get_service(self, provider_id: str, service_id: str):
        try:
            service = Service.objects.get(provider_id=provider_id, id=service_id)
        except Service.DoesNotExist as exc:
            raise NotFound("Service not offered by provider") from exc
        return {
            "id": str(service.id),
            "name": service.name,
            "base_price_cents": service.base_price_cents,
            "hair_length_adjustments": service.hair_length_adjustments or {},
            "meche_bonus_cents": service.meche_bonus_cents,
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
