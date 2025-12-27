from django.db import transaction

from chateaurose.domain.entities.marketing_import import ImportResult, MarketingImportBundle
from chateaurose.domain.repositories.marketing import MarketingContentRepository
from interface.models import (
    MarketingCity,
    MarketingDistrict,
    MarketingService,
    MarketingServiceCity,
    MarketingServiceCityImage,
    MarketingServiceImage,
)


class DjangoMarketingContentRepository(MarketingContentRepository):
    @staticmethod
    def _is_url(path: str | None) -> bool:
        if not path:
            return False
        return str(path).startswith(("http://", "https://", "/static/"))

    def bulk_import(self, bundle: MarketingImportBundle) -> ImportResult:
        with transaction.atomic():
            service_map = self._upsert_services(bundle)
            city_map = self._upsert_cities(bundle)
            overrides_count = self._upsert_overrides(bundle, service_map, city_map)

        return ImportResult(
            services_count=len(bundle.services),
            cities_count=len(bundle.cities),
            districts_count=sum(len(city.districts) for city in bundle.cities),
            overrides_count=overrides_count,
        )

    def _upsert_services(self, bundle: MarketingImportBundle):
        service_map = {}
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
            service_map[service.slug] = obj
        return service_map

    def _upsert_cities(self, bundle: MarketingImportBundle):
        city_map = {}
        for city in bundle.cities:
            city_obj, _ = MarketingCity.objects.get_or_create(
                slug=city.slug,
                defaults={
                    "name": city.name,
                    "intro": city.intro,
                    "main_image": city.main_image,
                    "main_image_url": city.main_image_url,
                    "meta_description": city.meta_description,
                },
            )
            city_obj.name = city.name
            city_obj.intro = city.intro
            city_obj.main_image = city.main_image or None
            city_obj.main_image_url = city.main_image_url or (city.main_image if self._is_url(city.main_image) else "")
            city_obj.meta_description = city.meta_description
            city_obj.save()
            city_obj.districts.all().delete()
            for district in city.districts:
                MarketingDistrict.objects.create(
                    city=city_obj,
                    name=district.name,
                    slug=district.slug,
                    intro=district.intro,
                    meta_description=district.meta_description,
                )
            city_map[city.slug] = city_obj
        return city_map

    def _upsert_overrides(self, bundle: MarketingImportBundle, service_map, city_map):
        overrides_count = 0
        for override in bundle.service_city_overrides:
            service_obj = service_map.get(override.service_slug)
            city_obj = city_map.get(override.city_slug)
            if not service_obj or not city_obj:
                continue
            obj, _ = MarketingServiceCity.objects.get_or_create(
                service=service_obj,
                city=city_obj,
                defaults={
                    "intro": override.intro,
                    "highlights": override.highlights,
                    "main_image": override.main_image,
                    "main_image_url": override.main_image_url,
                    "meta_description": override.meta_description,
                },
            )
            obj.intro = override.intro
            obj.highlights = override.highlights
            obj.main_image = override.main_image or None
            obj.main_image_url = override.main_image_url or (
                override.main_image if self._is_url(override.main_image) else ""
            )
            obj.meta_description = override.meta_description
            obj.save()
            obj.images.all().delete()
            for order, image_path in enumerate(override.gallery):
                image_kwargs = {"service_city": obj, "order": order}
                if self._is_url(image_path):
                    image_kwargs["image_url"] = image_path
                else:
                    image_kwargs["image"] = image_path
                MarketingServiceCityImage.objects.create(**image_kwargs)
            overrides_count += 1
        return overrides_count
