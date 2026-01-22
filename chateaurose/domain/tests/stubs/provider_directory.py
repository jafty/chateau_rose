class InMemoryProviderDirectory:
    def __init__(self, providers):
        self.providers = providers

    def get_provider_contact(self, provider_id):
        return self.providers[provider_id]
