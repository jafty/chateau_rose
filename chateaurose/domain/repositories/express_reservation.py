from typing import Protocol

from chateaurose.domain.entities.express_reservation import ExpressServiceChoice


class ExpressReservationCatalog(Protocol):
    def list_visible_sub_services(self) -> list[ExpressServiceChoice]:
        """Return all visible sub-services available for express reservation."""
