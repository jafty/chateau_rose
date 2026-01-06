class InMemoryProviderCatalog:
    LOCATION_MODE_SALON_ONLY = "salon_only"
    LOCATION_MODE_CLIENT_HOME_ONLY = "client_home_only"
    LOCATION_MODE_HYBRID = "hybrid"
    SALON_LOCATION_LABEL = "Salon"

    def __init__(self, services_by_provider, zones_by_provider, location_modes=None):
        self.services_by_provider = services_by_provider
        self.zones_by_provider = zones_by_provider
        self.location_modes = location_modes or {
            provider_id: self.LOCATION_MODE_CLIENT_HOME_ONLY
            for provider_id in services_by_provider.keys()
        }

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
