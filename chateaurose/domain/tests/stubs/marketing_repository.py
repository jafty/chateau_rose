from chateaurose.domain.entities.marketing_import import (
    ImportResult,
    MarketingImportBundle,
)
from chateaurose.domain.repositories.marketing import MarketingContentRepository


class InMemoryMarketingContentRepository(MarketingContentRepository):
    def __init__(self):
        self.received_bundle: MarketingImportBundle | None = None
        self.calls = 0

    def bulk_import(self, bundle: MarketingImportBundle) -> ImportResult:
        self.calls += 1
        self.received_bundle = bundle
        return ImportResult(
            services_count=len(bundle.services),
            cities_count=len(bundle.cities),
            districts_count=sum(len(city.districts) for city in bundle.cities),
            overrides_count=len(bundle.service_city_overrides),
        )
