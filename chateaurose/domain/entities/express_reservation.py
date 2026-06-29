from dataclasses import dataclass


@dataclass(frozen=True)
class ExpressServiceChoice:
    service_name: str
    service_slug: str
    sub_service_name: str
    sub_service_slug: str
