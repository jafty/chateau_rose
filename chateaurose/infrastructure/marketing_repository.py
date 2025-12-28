from django.db import transaction

from chateaurose.domain.entities.marketing_import import ImportResult, MarketingImportBundle
from chateaurose.domain.repositories.marketing import MarketingContentRepository
from interface.models import MarketingService, MarketingServiceImage


class DjangoMarketingContentRepository(MarketingContentRepository):
    @staticmethod
    def _is_url(path: str | None) -> bool:
        if not path:
            return False
        return str(path).startswith(("http://", "https://", "/static/"))

    def bulk_import(self, bundle: MarketingImportBundle) -> ImportResult:
        with transaction.atomic():
            self._upsert_services(bundle)

        return ImportResult(services_count=len(bundle.services))

    def _upsert_services(self, bundle: MarketingImportBundle):
        for service in bundle.services:
            obj, _ = MarketingService.objects.get_or_create(
                slug=service.slug,
                defaults={
                    "name": service.name,
                    "intro": service.intro,
                    "highlights": service.highlights,
                    "main_image": service.main_image,
                    "main_image_url": service.main_image_url,
                    "meta_description": service.meta_description,
                },
            )
            obj.name = service.name
            obj.intro = service.intro
            obj.highlights = service.highlights
            obj.main_image = service.main_image or None
            obj.main_image_url = service.main_image_url or (service.main_image if self._is_url(service.main_image) else "")
            obj.meta_description = service.meta_description
            obj.save()
            obj.images.all().delete()
            for order, image_path in enumerate(service.gallery):
                image_kwargs = {"service": obj, "order": order}
                if self._is_url(image_path):
                    image_kwargs["image_url"] = image_path
                else:
                    image_kwargs["image"] = image_path
                MarketingServiceImage.objects.create(**image_kwargs)
        return None
