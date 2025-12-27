from dataclasses import dataclass, field
from typing import List, Optional


DEFAULT_INTRO_TEMPLATE = (
    "{service_name} réalisées par des coiffeuses afro sélectionnées, avec prise de rendez-vous simplifiée."
)


def _default_highlights(service_name: str) -> List[str]:
    return [
        "Temps de réponse rapide : on vous propose un créneau en quelques minutes.",
        "Brief clair : longueur, mèches fournies ou non, inspirations via photos ou liens.",
        f"Artistes spécialisés pour {service_name.lower()} à domicile ou en salon partenaire.",
    ]


@dataclass
class ServiceContent:
    name: str
    intro: str = ""
    highlights: List[str] = field(default_factory=list)
    main_image: Optional[str] = None
    gallery: List[str] = field(default_factory=list)
    meta_description: str = ""


@dataclass
class CityContent:
    name: str
    intro: str = ""
    main_image: Optional[str] = None
    meta_description: str = ""


@dataclass
class OverrideContent:
    intro: str = ""
    highlights: List[str] = field(default_factory=list)
    main_image: Optional[str] = None
    gallery: List[str] = field(default_factory=list)
    meta_description: str = ""


@dataclass
class MarketingContent:
    intro: str
    city_intro: str
    highlights: List[str]
    hero_image: Optional[str]
    gallery: List[str]
    meta_description: str


def _intro(service: ServiceContent) -> str:
    return service.intro or DEFAULT_INTRO_TEMPLATE.format(service_name=service.name)


def _city_intro(
    service_intro: str,
    city: Optional[CityContent],
    override: Optional[OverrideContent],
    district_name: Optional[str],
) -> str:
    if override and override.intro:
        return override.intro
    if city:
        city_name = city.name
        location = f"{city_name}"
        if district_name:
            location = f"{city_name} (quartier {district_name})"
        return f"{service_intro} Nous intervenons à {location} et ses quartiers avec des artistes locaux."
    return "Prestataires mobiles ou en salon sur Toulouse métropole."


def _highlights(
    service: ServiceContent,
    city: Optional[CityContent],
    override: Optional[OverrideContent],
    district_name: Optional[str],
) -> List[str]:
    if override and override.highlights:
        return override.highlights

    highlights = service.highlights or _default_highlights(service.name)
    if city:
        suffix = city.name
        if district_name:
            suffix = f"{district_name}, {city.name}"
        return [f"{highlight} ({suffix})" for highlight in highlights]
    return highlights


def _meta_description(
    service: ServiceContent,
    city: Optional[CityContent],
    override: Optional[OverrideContent],
    district_name: Optional[str],
) -> str:
    if override and override.meta_description:
        return override.meta_description
    if service.meta_description:
        return service.meta_description
    if city and district_name:
        return f"{service.name} par des artistes afro à {district_name}, {city.name}. Réservation en quelques minutes."
    if city:
        return f"{service.name} par des coiffeuses afro à {city.name} et ses quartiers, réservation rapide."
    return f"{service.name} par des coiffeuses afro sélectionnées. Réservation rapide à Toulouse et alentours."


def _hero_image(service: ServiceContent, city: Optional[CityContent], override: Optional[OverrideContent]) -> Optional[str]:
    if override and override.main_image:
        return override.main_image
    if city and city.main_image:
        return city.main_image
    return service.main_image


def _gallery(service: ServiceContent, override: Optional[OverrideContent]) -> List[str]:
    if override and override.gallery:
        return override.gallery
    return service.gallery


def build_marketing_content(
    *,
    service: ServiceContent,
    city: Optional[CityContent] = None,
    override: Optional[OverrideContent] = None,
    district_name: Optional[str] = None,
) -> MarketingContent:
    service_intro = override.intro if (override and override.intro and city) else _intro(service)
    city_intro = _city_intro(service_intro, city, override, district_name)
    highlights = _highlights(service, city, override, district_name)
    hero_image = _hero_image(service, city, override)
    gallery = _gallery(service, override)
    meta_description = _meta_description(service, city, override, district_name)

    return MarketingContent(
        intro=service_intro,
        city_intro=city_intro,
        highlights=highlights,
        hero_image=hero_image,
        gallery=gallery,
        meta_description=meta_description,
    )
