from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from chateaurose.domain.exceptions import InvalidState, PermissionError, ValidationError
from chateaurose.domain.services.booking_deadlines import (
    add_response_hours,
    initial_provider_deadline,
    require_minimum_notice,
)
from chateaurose.domain.use_cases import bounty

UTC = timezone.utc
NOW = datetime(2026, 9, 1, 20, tzinfo=UTC)


def booking(status="WAITING_PROVIDER_ASSIGNMENT"):
    return SimpleNamespace(
        status=status,
        updated_at=NOW,
        state_entered_at=NOW,
        process_expires_at=NOW + timedelta(days=6),
        provider_id=None,
        service_id=None,
        proposed_date=None,
        proposed_price_cents=None,
        provider_price_estimate_cents=10000,
        estimated_price_cents=11500,
        chateau_rose_fee_cents=1500,
    )


def opportunity(status="OPEN"):
    return SimpleNamespace(
        status=status, response_deadline_at=NOW + timedelta(days=2), closed_at=None
    )


def offer(deadline=None):
    return SimpleNamespace(
        status="PENDING_CLIENT",
        client_deadline_at=deadline or NOW + timedelta(days=1),
        provider_id="2",
        service_id="8",
        proposed_date="2026-09-05T10:00:00+00:00",
        proposed_price_cents=12000,
        decided_at=None,
    )


def test_minimum_notice_and_priority_windows():
    with pytest.raises(ValidationError):
        require_minimum_notice(
            desired_at=NOW + timedelta(hours=23, minutes=59), now=NOW
        )
    require_minimum_notice(desired_at=NOW + timedelta(hours=24), now=NOW)
    assert initial_provider_deadline(
        now=NOW, desired_at=NOW + timedelta(hours=30)
    ) == datetime(2026, 9, 2, 10, tzinfo=UTC)
    assert initial_provider_deadline(
        now=NOW, desired_at=NOW + timedelta(days=3)
    ) == datetime(2026, 9, 2, 18, tzinfo=UTC)
    assert add_response_hours(datetime(2026, 9, 1, 23, tzinfo=UTC), 4) == datetime(
        2026, 9, 2, 12, tzinfo=UTC
    )


def test_bounty_requires_exact_sub_service():
    with pytest.raises(ValidationError):
        bounty.open_bounty(
            booking=booking(), reason="GENERIC", now=NOW, sub_service_id=None
        )


def test_open_bounty_has_48_response_hour_deadline():
    result = bounty.open_bounty(
        booking=booking(), reason="GENERIC", now=NOW, sub_service_id="3"
    )
    assert result["booking"].status == "BOUNTY_OPEN"
    assert result["deadline"] == datetime(2026, 9, 5, 12, tzinfo=UTC)


def test_only_first_eligible_offer_is_accepted():
    item, campaign = booking("BOUNTY_OPEN"), opportunity()
    deadline = bounty.submit_first_offer(
        booking=item,
        opportunity=campaign,
        terms=bounty.OfferTerms("2", "8", "2026-09-05T10:00:00+00:00", 12000),
        now=NOW,
        provider_is_eligible=True,
        desired_at=NOW + timedelta(days=4),
    )
    assert item.status == "BOUNTY_CLIENT_VALIDATION"
    assert campaign.status == "OFFERED"
    assert deadline == datetime(2026, 9, 3, 16, tzinfo=UTC)
    with pytest.raises(InvalidState):
        bounty.submit_first_offer(
            booking=item,
            opportunity=campaign,
            terms=bounty.OfferTerms("3", "9", "x", 1),
            now=NOW,
            provider_is_eligible=True,
            desired_at=NOW + timedelta(days=4),
        )


def test_ineligible_provider_and_short_notice_are_rejected():
    with pytest.raises(PermissionError):
        bounty.submit_first_offer(
            booking=booking("BOUNTY_OPEN"),
            opportunity=opportunity(),
            terms=bounty.OfferTerms("2", "8", "x", 1),
            now=NOW,
            provider_is_eligible=False,
            desired_at=NOW + timedelta(days=3),
        )
    with pytest.raises(ValidationError):
        bounty.submit_first_offer(
            booking=booking("BOUNTY_OPEN"),
            opportunity=opportunity(),
            terms=bounty.OfferTerms("2", "8", "x", 1),
            now=NOW,
            provider_is_eligible=True,
            desired_at=NOW + timedelta(hours=23),
        )


def test_client_accepts_exact_terms_without_changing_fee():
    item, proposed = booking("BOUNTY_CLIENT_VALIDATION"), offer()
    bounty.decide_offer(booking=item, offer=proposed, decision="accept", now=NOW)
    assert item.status == "CONFIRMED"
    assert item.provider_id == "2"
    assert item.proposed_price_cents == 12000
    assert item.chateau_rose_fee_cents == 1500
    assert item.estimated_price_cents == 13500


def test_client_rejection_cancels_without_second_bounty():
    item, proposed = booking("BOUNTY_CLIENT_VALIDATION"), offer()
    bounty.decide_offer(booking=item, offer=proposed, decision="reject", now=NOW)
    assert item.status == "CANCELLED"
    assert proposed.status == "REJECTED"


def test_expired_client_offer_cannot_be_accepted():
    with pytest.raises(InvalidState):
        bounty.decide_offer(
            booking=booking("BOUNTY_CLIENT_VALIDATION"),
            offer=offer(NOW),
            decision="accept",
            now=NOW,
        )
