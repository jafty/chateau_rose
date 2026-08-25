from dataclasses import dataclass

from chateaurose.domain.exceptions import InvalidState, PermissionError, ValidationError
from chateaurose.domain.services.booking_deadlines import (
    bounded_deadline,
    require_minimum_notice,
)


@dataclass(frozen=True)
class OfferTerms:
    provider_id: str
    service_id: str
    proposed_date: str
    proposed_price_cents: int
    message: str = ""


def open_bounty(*, booking, reason: str, now, sub_service_id: str | None):
    if booking.status not in (
        "WAITING_PROVIDER_ASSIGNMENT",
        "SUBMITTED",
        "AWAITING_ALTERNATIVE_PROVIDER",
    ):
        raise InvalidState("Booking cannot enter bounty from its current state")
    if not sub_service_id:
        raise ValidationError(
            "Le service prestataire n'est lié à aucun sous-service marketing."
        )
    booking.status = "BOUNTY_OPEN"
    booking.updated_at = booking.state_entered_at = now
    return {
        "booking": booking,
        "reason": reason,
        "sub_service_id": str(sub_service_id),
        "deadline": bounded_deadline(
            start=now, response_hours=48, process_expires_at=booking.process_expires_at
        ),
    }


def submit_first_offer(
    *,
    booking,
    opportunity,
    terms: OfferTerms,
    now,
    provider_is_eligible: bool,
    desired_at,
):
    if booking.status != "BOUNTY_OPEN" or opportunity.status != "OPEN":
        raise InvalidState("Cette opportunité a déjà reçu une proposition.")
    if now >= opportunity.response_deadline_at:
        raise InvalidState("Cette opportunité a expiré.")
    if not provider_is_eligible:
        raise PermissionError(
            "Cette prestataire n'est pas éligible à cette opportunité."
        )
    if terms.proposed_price_cents < 0:
        raise ValidationError("Le tarif proposé doit être positif.")
    require_minimum_notice(desired_at=desired_at, now=now)
    opportunity.status, opportunity.closed_at = "OFFERED", now
    booking.status, booking.updated_at, booking.state_entered_at = (
        "BOUNTY_CLIENT_VALIDATION",
        now,
        now,
    )
    return bounded_deadline(
        start=now, response_hours=24, process_expires_at=booking.process_expires_at
    )


def accept_unchanged_request(
    *,
    booking,
    opportunity,
    provider_id,
    service_id,
    now,
    provider_is_eligible: bool,
    service_matches_request: bool,
    desired_at,
):
    """Confirm an open bounty without allowing any of its terms to be replaced."""
    if booking.status != "BOUNTY_OPEN" or opportunity.status != "OPEN":
        raise InvalidState("Cette opportunité n'est plus disponible.")
    if now >= opportunity.response_deadline_at:
        raise InvalidState("Cette opportunité a expiré.")
    if not provider_is_eligible or not service_matches_request:
        raise PermissionError(
            "Cette prestation n'est pas éligible à cette opportunité."
        )
    require_minimum_notice(desired_at=desired_at, now=now)

    opportunity.status, opportunity.closed_at = "OFFERED", now
    booking.provider_id, booking.service_id = provider_id, service_id
    booking.status = "CONFIRMED"
    booking.updated_at = booking.state_entered_at = now
    return booking


def decide_offer(*, booking, offer, decision: str, now):
    if booking.status != "BOUNTY_CLIENT_VALIDATION" or offer.status != "PENDING_CLIENT":
        raise InvalidState("Cette proposition n'est plus disponible.")
    if now >= offer.client_deadline_at:
        raise InvalidState("Cette proposition a expiré.")
    if decision not in ("accept", "reject"):
        raise ValidationError("Décision inconnue.")
    offer.decided_at = booking.updated_at = booking.state_entered_at = now
    if decision == "reject":
        offer.status, booking.status = "REJECTED", "CANCELLED"
        return booking
    offer.status = "ACCEPTED"
    booking.provider_id, booking.service_id = offer.provider_id, offer.service_id
    booking.proposed_date, booking.proposed_price_cents = (
        offer.proposed_date,
        offer.proposed_price_cents,
    )
    booking.provider_price_estimate_cents = offer.proposed_price_cents
    booking.estimated_price_cents = (
        offer.proposed_price_cents + booking.chateau_rose_fee_cents
    )
    booking.status = "CONFIRMED"
    return booking
