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
        return ImportResult(services_count=len(bundle.services))
