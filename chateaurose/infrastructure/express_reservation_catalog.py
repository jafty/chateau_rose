from chateaurose.domain.entities.express_reservation import ExpressServiceChoice
from interface.models import MarketingSubService


class DjangoExpressReservationCatalog:
    def list_visible_sub_services(self) -> list[ExpressServiceChoice]:
        sub_services = (
            MarketingSubService.objects.filter(is_visible=True)
            .select_related("service")
            .order_by("service__homepage_order", "service__name", "order", "name")
        )
        return [
            ExpressServiceChoice(
                service_name=sub_service.service.name,
                service_slug=sub_service.service.slug,
                sub_service_name=sub_service.name,
                sub_service_slug=sub_service.slug,
            )
            for sub_service in sub_services
        ]
