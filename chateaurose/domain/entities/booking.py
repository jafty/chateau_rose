from dataclasses import dataclass
from datetime import datetime


@dataclass
class BookingRequest:
    id: str
    provider_id: str | None
    service_id: str | None
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
    booking_kind: str = "PROVIDER_SELECTED"
    requested_marketing_service_id: str | None = None
    requested_marketing_sub_service_id: str | None = None
    requested_service_label_snapshot: str = ""
    requested_options: list[str] | None = None
    provider_price_estimate_cents: int | None = None
    chateau_rose_fee_cents: int = 0
    amount_due_now_cents: int = 0
    payment_status: str = "REQUIRES_PAYMENT"
