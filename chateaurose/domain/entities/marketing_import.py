from dataclasses import dataclass, field
from typing import List


@dataclass
class DistrictImport:
    city_slug: str
    slug: str
    name: str
    intro: str = ""
    meta_description: str = ""


@dataclass
class CityImport:
    slug: str
    name: str
    intro: str = ""
    main_image: str | None = None
    main_image_url: str | None = None
    meta_description: str = ""
    districts: List[DistrictImport] = field(default_factory=list)


@dataclass
class ServiceImport:
    slug: str
    name: str
    intro: str = ""
    highlights: List[str] = field(default_factory=list)
    main_image: str | None = None
    main_image_url: str | None = None
    meta_description: str = ""
    gallery: List[str] = field(default_factory=list)


@dataclass
class ServiceCityOverrideImport:
    service_slug: str
    city_slug: str
    intro: str = ""
    highlights: List[str] = field(default_factory=list)
    main_image: str | None = None
    main_image_url: str | None = None
    meta_description: str = ""
    gallery: List[str] = field(default_factory=list)


@dataclass
class MarketingImportBundle:
    services: List[ServiceImport]
    cities: List[CityImport]
    service_city_overrides: List[ServiceCityOverrideImport]


@dataclass
class ImportResult:
    services_count: int
    cities_count: int
    districts_count: int
    overrides_count: int
