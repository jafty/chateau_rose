from dataclasses import dataclass, field
from typing import List


@dataclass
class ServiceImport:
    slug: str
    name: str
    intro: str = ""
    short_intro: str = ""
    long_description: str = ""
    long_title: str = ""
    highlights: List[str] = field(default_factory=list)
    main_image: str | None = None
    main_image_url: str | None = None
    meta_description: str = ""
    gallery: List[str] = field(default_factory=list)
@dataclass
class MarketingImportBundle:
    services: List[ServiceImport]
    cities: List[object] = field(default_factory=list)
    service_city_overrides: List[object] = field(default_factory=list)


@dataclass
class ImportResult:
    services_count: int
