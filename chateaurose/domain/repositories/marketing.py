from abc import ABC, abstractmethod

from chateaurose.domain.entities.marketing_import import ImportResult, MarketingImportBundle


class MarketingContentRepository(ABC):
    """Port for bulk-importing marketing content (services, cities, overrides)."""

    @abstractmethod
    def bulk_import(self, bundle: MarketingImportBundle) -> ImportResult:
        """Persist the validated bundle atomically and return an import summary."""

