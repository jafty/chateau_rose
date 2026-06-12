from datetime import datetime


class InMemoryProviderCatalog:
    LOCATION_MODE_SALON_ONLY = "salon_only"
    LOCATION_MODE_CLIENT_HOME_ONLY = "client_home_only"
    LOCATION_MODE_HYBRID = "hybrid"
    SALON_LOCATION_LABEL = "Salon"

    def __init__(self, services_by_provider, zones_by_provider, location_modes=None, blocked_slots=None):
        self.services_by_provider = services_by_provider
        self.zones_by_provider = zones_by_provider
        self.location_modes = location_modes or {
            provider_id: self.LOCATION_MODE_CLIENT_HOME_ONLY
            for provider_id in services_by_provider.keys()
        }
        self.blocked_slots = blocked_slots or {}

    def get_service(self, provider_id, service_id):
        return self.services_by_provider[provider_id][service_id]

    def provider_covers_zone(self, provider_id, zone):
        mode = self.location_modes.get(
            provider_id, self.LOCATION_MODE_CLIENT_HOME_ONLY
        )

        if mode == self.LOCATION_MODE_SALON_ONLY:
            return zone == self.SALON_LOCATION_LABEL

        if mode == self.LOCATION_MODE_HYBRID and zone == self.SALON_LOCATION_LABEL:
            return True

        return zone in self.zones_by_provider.get(provider_id, set())

    def provider_has_blocked_slot(self, provider_id, desired_date):
        appointment_at = datetime.fromisoformat(str(desired_date).replace("Z", "+00:00"))
        for starts_at, ends_at in self.blocked_slots.get(provider_id, []):
            if starts_at <= appointment_at < ends_at:
                return True
        return False

    def provider_service_matches_intent(
        self,
        *,
        provider_id,
        service_id,
        requested_marketing_service_id=None,
        requested_marketing_sub_service_id=None,
    ):
        service = self.get_service(provider_id, service_id)
        if requested_marketing_sub_service_id:
            return str(requested_marketing_sub_service_id) in {str(item) for item in service.get("marketing_sub_service_ids", [])}
        if requested_marketing_service_id:
            return str(service.get("marketing_service_id")) == str(requested_marketing_service_id)
        return True
