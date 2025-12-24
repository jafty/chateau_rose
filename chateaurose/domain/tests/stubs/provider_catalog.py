class InMemoryProviderCatalog:
    def __init__(self, services_by_provider, zones_by_provider):
        self.services_by_provider = services_by_provider
        self.zones_by_provider = zones_by_provider

    def get_service(self, provider_id, service_id):
        return self.services_by_provider[provider_id][service_id]

    def provider_covers_zone(self, provider_id, zone):
        return zone in self.zones_by_provider[provider_id]
