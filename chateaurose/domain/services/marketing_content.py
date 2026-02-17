from dataclasses import dataclass, field
from typing import List, Optional


DEFAULT_INTRO_TEMPLATE = (
    "{service_name} réalisées par des coiffeuses afro sélectionnées, avec prise de rendez-vous simplifiée."
)
DEFAULT_LOCATION_INTRO = "Prestataires mobiles ou en salon sur Toulouse métropole."


def _default_highlights(service_name: str, location: Optional[str]) -> List[str]:
    base = [
        "Temps de réponse rapide : on vous propose un créneau en quelques minutes.",
        "Brief clair : longueur, mèches fournies ou non, inspirations via photos ou liens.",
        f"Artistes spécialisés pour {service_name.lower()} à domicile ou en salon partenaire.",
    ]
    if location:
        return [f"{highlight} ({location})" for highlight in base]
    return base


def _with_location(highlights: List[str], location: Optional[str]) -> List[str]:
    if not location:
        return list(highlights)

    normalized_location = location.lower()
    return [
        highlight
        if normalized_location in highlight.lower()
        else f"{highlight} ({location})"
        for highlight in highlights
    ]


@dataclass
class GalleryImage:
    url: str
    caption: str = ""


@dataclass
class ServiceContent:
    name: str
    intro: str = ""
    short_intro: str = ""
    long_description: str = ""
    long_title: str = ""
    highlights: List[str] = field(default_factory=list)
    main_image: Optional[str] = None
    gallery: List[GalleryImage] = field(default_factory=list)
    meta_description: str = ""


@dataclass
class MarketingContent:
    intro: str
    short_intro: str
    long_description: str
    long_title: str
    location_intro: str
    highlights: List[str]
    hero_image: Optional[str]
    gallery: List[GalleryImage]
    meta_description: str


def build_marketing_content(
    *,
    service: ServiceContent,
    location_name: Optional[str] = None,
) -> MarketingContent:
    intro = service.intro or DEFAULT_INTRO_TEMPLATE.format(service_name=service.name)
    short_intro = service.short_intro or intro
    long_description = service.long_description
    long_title = service.long_title or service.name
    if location_name:
        location_intro = f"Disponible à {location_name} et dans les environs."
    else:
        location_intro = DEFAULT_LOCATION_INTRO

    highlights = _with_location(
        service.highlights or _default_highlights(service.name, location_name),
        location_name,
    )
    meta_description = service.meta_description
    if not meta_description:
        if location_name:
            meta_description = (
                f"{service.name} par des coiffeuses afro à {location_name}. Réservation rapide et artistes vérifiées."
            )
        else:
            meta_description = (
                f"{service.name} par des coiffeuses afro sélectionnées. Réservation rapide à Toulouse et alentours."
            )

    return MarketingContent(
        intro=intro,
        short_intro=short_intro,
        long_description=long_description,
        long_title=long_title,
        location_intro=location_intro,
        highlights=highlights,
        hero_image=service.main_image,
        gallery=service.gallery,
        meta_description=meta_description,
    )
