from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


LABELS = {5: "Excellent", 4: "Très bien", 3: "Bien"}
MIN_BADGE_REVIEWS = 3
MIN_BADGE_AVERAGE = 4
MAX_INVITATION_REMINDERS = 2
REMINDER_INTERVAL_DAYS = 3


@dataclass(frozen=True)
class BookingReviewState:
    status: str
    appointment_at: object | None
    has_review: bool = False
    has_incident_response: bool = False
    invitations_sent: int = 0
    last_invitation_sent_at: object | None = None


def rating_label(rating: int) -> str:
    return LABELS.get(int(rating), "")


def can_publish_review(*, consent_given: bool, moderation_status: str) -> bool:
    return bool(consent_given) and moderation_status == "approved"


def provider_review_badge(ratings: list[int]) -> dict | None:
    if len(ratings) <= MIN_BADGE_REVIEWS:
        return None
    average = sum(ratings) / len(ratings)
    if average < MIN_BADGE_AVERAGE:
        return None
    rounded = round(average)
    return {"label": rating_label(rounded), "count": len(ratings)}


def can_create_review(*, booking_status: str, appointment_at, now, already_reviewed: bool, consent_given: bool) -> tuple[bool, str]:
    if booking_status != "CONFIRMED":
        return False, "booking_not_confirmed"
    if appointment_at is None or appointment_at > now:
        return False, "appointment_not_completed"
    if already_reviewed:
        return False, "duplicate_review"
    if not consent_given:
        return False, "missing_consent"
    return True, "eligible"


def invitation_due(state: BookingReviewState, now) -> tuple[bool, str]:
    if state.status != "CONFIRMED":
        return False, "booking_not_confirmed"
    if state.appointment_at is None or state.appointment_at + timedelta(days=1) > now:
        return False, "too_early"
    if state.has_review:
        return False, "review_recorded"
    if state.has_incident_response:
        return False, "incident_recorded"
    if state.invitations_sent == 0:
        return True, "first_request_due"
    if state.invitations_sent > MAX_INVITATION_REMINDERS:
        return False, "max_reminders_reached"
    if state.last_invitation_sent_at and state.last_invitation_sent_at + timedelta(days=REMINDER_INTERVAL_DAYS) <= now:
        return True, "reminder_due"
    return False, "reminder_not_due"
