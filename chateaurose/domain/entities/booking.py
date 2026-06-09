from dataclasses import dataclass
from datetime import datetime


@dataclass
class BookingRequest:
    id: str
    provider_id: str
    service_id: str
    client_contact: dict
    location: str
    desired_date: str
    hair_length: str
    meche: bool
    current_hair_picture: str
    inspiration_pictures: list
    free_text: str
    estimated_price_cents: int
    payment_auth_id: str
    status: str
    created_at: datetime
    alternative_requested_at: datetime | None = None
    general_adjustments: list[str] | None = None
    proposed_price_cents: int | None = None
    proposed_date: str | None = None
    updated_at: datetime | None = None
    location_preference: str | None = None
    client_address: str | None = None
