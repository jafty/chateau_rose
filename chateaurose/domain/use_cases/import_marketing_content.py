import json
from typing import Dict, List, Tuple

from chateaurose.domain.entities.marketing_import import (
    CityImport,
    DistrictImport,
    ImportResult,
    MarketingImportBundle,
    ServiceCityOverrideImport,
    ServiceImport,
)
from chateaurose.domain.exceptions import ValidationError
from chateaurose.domain.repositories.marketing import MarketingContentRepository


def _require_string(payload: dict, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Missing or invalid field: {field}")
    return value.strip()


def _list_of_strings(value, field_name: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError(f"{field_name} must be a list of strings")
    return value


def _merge_optional(current: str | None, new: str | None, field: str) -> str | None:
    if not new:
        return current
    if current and current != new:
        raise ValidationError(f"Conflicting {field} definitions")
    return new


def _parse_city(
    city_payload: dict,
    *,
    city_map: Dict[str, CityImport],
    district_map: Dict[str, Dict[str, DistrictImport]],
) -> CityImport:
    if not isinstance(city_payload, dict):
        raise ValidationError("Each city entry must be an object")
    city_slug = _require_string(city_payload, "slug")
    city_name = _require_string(city_payload, "name")

    existing_city = city_map.get(city_slug)
    intro = city_payload.get("intro", "") if isinstance(city_payload.get("intro", ""), str) else ""
    main_image = city_payload.get("main_image") if isinstance(city_payload.get("main_image"), str) else None
    main_image_url = city_payload.get("main_image_url") if isinstance(city_payload.get("main_image_url"), str) else None
    meta_description = (
        city_payload.get("meta_description", "")
        if isinstance(city_payload.get("meta_description", ""), str)
        else ""
    )

    if existing_city:
        existing_city.name = _merge_optional(existing_city.name, city_name, f"city {city_slug} name") or city_name
        existing_city.intro = _merge_optional(existing_city.intro, intro, f"city {city_slug} intro") or existing_city.intro
        existing_city.main_image = _merge_optional(existing_city.main_image, main_image, f"city {city_slug} main_image")
        existing_city.main_image_url = _merge_optional(
            existing_city.main_image_url, main_image_url, f"city {city_slug} main_image_url"
        )
        existing_city.meta_description = (
            _merge_optional(existing_city.meta_description, meta_description, f"city {city_slug} meta_description")
            or existing_city.meta_description
        )
        city_obj = existing_city
    else:
        city_obj = CityImport(
            slug=city_slug,
            name=city_name,
            intro=intro,
            main_image=main_image,
            main_image_url=main_image_url,
            meta_description=meta_description,
            districts=[],
        )
        city_map[city_slug] = city_obj

    districts_payload = city_payload.get("districts", [])
    if districts_payload:
        if not isinstance(districts_payload, list):
            raise ValidationError("districts must be a list")
        district_slug_map = district_map.setdefault(city_slug, {})
        for district_payload in districts_payload:
            if not isinstance(district_payload, dict):
                raise ValidationError("Each district must be an object")
            district_slug = _require_string(district_payload, "slug")
            district_name = _require_string(district_payload, "name")
            intro_value = (
                district_payload.get("intro", "")
                if isinstance(district_payload.get("intro", ""), str)
                else ""
            )
            meta_value = (
                district_payload.get("meta_description", "")
                if isinstance(district_payload.get("meta_description", ""), str)
                else ""
            )
            existing_district = district_slug_map.get(district_slug)
            if existing_district and existing_district.name != district_name:
                raise ValidationError(f"Conflicting district definition for {district_slug}")
            if not existing_district:
                district_obj = DistrictImport(
                    city_slug=city_slug,
                    slug=district_slug,
                    name=district_name,
                    intro=intro_value,
                    meta_description=meta_value,
                )
                district_slug_map[district_slug] = district_obj
                city_obj.districts.append(district_obj)

    return city_obj


def _parse_override(
    override_payload: dict | None,
    *,
    service_slug: str,
    city_slug: str,
) -> ServiceCityOverrideImport | None:
    if not override_payload:
        return None
    if not isinstance(override_payload, dict):
        raise ValidationError("override must be an object")
    highlights = _list_of_strings(override_payload.get("highlights", []), f"override({service_slug},{city_slug}).highlights")
    gallery = _list_of_strings(override_payload.get("gallery", []), f"override({service_slug},{city_slug}).gallery")
    intro = override_payload.get("intro", "") if isinstance(override_payload.get("intro", ""), str) else ""
    main_image = override_payload.get("main_image") if isinstance(override_payload.get("main_image"), str) else None
    main_image_url = override_payload.get("main_image_url") if isinstance(override_payload.get("main_image_url"), str) else None
    meta_description = (
        override_payload.get("meta_description", "")
        if isinstance(override_payload.get("meta_description", ""), str)
        else ""
    )
    return ServiceCityOverrideImport(
        service_slug=service_slug,
        city_slug=city_slug,
        intro=intro,
        highlights=highlights,
        main_image=main_image,
        main_image_url=main_image_url,
        meta_description=meta_description,
        gallery=gallery,
    )


def _parse_service(
    service_payload: dict,
    *,
    seen_services: set,
    city_map: Dict[str, CityImport],
    district_map: Dict[str, Dict[str, DistrictImport]],
) -> Tuple[ServiceImport, List[ServiceCityOverrideImport]]:
    if not isinstance(service_payload, dict):
        raise ValidationError("Each service entry must be an object")
    slug = _require_string(service_payload, "slug")
    if slug in seen_services:
        raise ValidationError(f"Duplicate service slug: {slug}")
    seen_services.add(slug)
    name = _require_string(service_payload, "name")

    highlights = _list_of_strings(service_payload.get("highlights", []), f"service({slug}).highlights")
    gallery = _list_of_strings(service_payload.get("gallery", []), f"service({slug}).gallery")
    intro = service_payload.get("intro", "") if isinstance(service_payload.get("intro", ""), str) else ""
    main_image = service_payload.get("main_image") if isinstance(service_payload.get("main_image"), str) else None
    main_image_url = (
        service_payload.get("main_image_url") if isinstance(service_payload.get("main_image_url"), str) else None
    )
    meta_description = (
        service_payload.get("meta_description", "")
        if isinstance(service_payload.get("meta_description", ""), str)
        else ""
    )

    service_obj = ServiceImport(
        slug=slug,
        name=name,
        intro=intro,
        highlights=highlights,
        main_image=main_image,
        main_image_url=main_image_url,
        meta_description=meta_description,
        gallery=gallery,
    )

    overrides: List[ServiceCityOverrideImport] = []
    cities_payload = service_payload.get("cities", [])
    if cities_payload:
        if not isinstance(cities_payload, list):
            raise ValidationError("cities must be a list")
        for city_payload in cities_payload:
            city_obj = _parse_city(city_payload, city_map=city_map, district_map=district_map)
            override = _parse_override(city_payload.get("override"), service_slug=slug, city_slug=city_obj.slug)
            if override:
                overrides.append(override)

    return service_obj, overrides


def execute(
    *, raw_content: str, repository: MarketingContentRepository, format: str = "json"
) -> ImportResult:
    if format != "json":
        raise ValidationError("Unsupported format. Only JSON is accepted currently.")
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid JSON payload") from exc

    if not isinstance(payload, dict) or "services" not in payload:
        raise ValidationError("Payload must be an object with a 'services' key")
    services_payload = payload["services"]
    if not isinstance(services_payload, list):
        raise ValidationError("'services' must be a list")
    if not services_payload:
        raise ValidationError("At least one service is required")

    city_map: Dict[str, CityImport] = {}
    district_map: Dict[str, Dict[str, DistrictImport]] = {}
    services: List[ServiceImport] = []
    overrides: List[ServiceCityOverrideImport] = []
    seen_services: set = set()

    for service_payload in services_payload:
        service_obj, service_overrides = _parse_service(
            service_payload,
            seen_services=seen_services,
            city_map=city_map,
            district_map=district_map,
        )
        services.append(service_obj)
        overrides.extend(service_overrides)

    bundle = MarketingImportBundle(
        services=services,
        cities=list(city_map.values()),
        service_city_overrides=overrides,
    )
    return repository.bulk_import(bundle)
