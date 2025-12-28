from typing import List

from chateaurose.domain.entities.marketing_import import ImportResult, MarketingImportBundle, ServiceImport
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


def _parse_service(service_payload: dict) -> ServiceImport:
    if not isinstance(service_payload, dict):
        raise ValidationError("Each service entry must be an object")
    return ServiceImport(
        slug=_require_string(service_payload, "slug"),
        name=_require_string(service_payload, "name"),
        intro=service_payload.get("intro", ""),
        highlights=_list_of_strings(service_payload.get("highlights"), "highlights"),
        main_image=service_payload.get("main_image") if isinstance(service_payload.get("main_image"), str) else None,
        main_image_url=service_payload.get("main_image_url")
        if isinstance(service_payload.get("main_image_url"), str)
        else None,
        meta_description=service_payload.get("meta_description", "")
        if isinstance(service_payload.get("meta_description", ""), str)
        else "",
        gallery=_list_of_strings(service_payload.get("gallery"), "gallery"),
    )


def execute(payload: dict, *, repository: MarketingContentRepository) -> ImportResult:
    if not isinstance(payload, dict):
        raise ValidationError("Payload must be an object")

    raw_services = payload.get("services")
    if raw_services is None:
        raise ValidationError("services is required")
    if not isinstance(raw_services, list):
        raise ValidationError("services must be a list")

    services = []
    seen_slugs = set()
    for service_payload in raw_services:
        service = _parse_service(service_payload)
        if service.slug in seen_slugs:
            raise ValidationError(f"Duplicate service slug: {service.slug}")
        seen_slugs.add(service.slug)
        services.append(service)

    bundle = MarketingImportBundle(services=services)
    return repository.bulk_import(bundle)
