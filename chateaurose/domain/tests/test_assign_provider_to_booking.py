from datetime import datetime, timezone

import pytest

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import ValidationError
from chateaurose.domain.tests.stubs.booking_repository import InMemoryBookingRepository
from chateaurose.domain.tests.stubs.clock import FixedClock
from chateaurose.domain.tests.stubs.notifier import InMemoryNotifier
from chateaurose.domain.tests.stubs.provider_catalog import InMemoryProviderCatalog
from chateaurose.domain.use_cases import assign_provider_to_booking


def _service(**overrides):
    data = {
        "id": "svc-1",
        "name": "Vanilles",
        "base_price_cents": 10000,
        "hair_length_adjustments": {"standard": 0},
        "general_adjustments": {"extra-long": 2500},
        "meche_bonus_cents": 0,
        "at_home_bonus_cents": 0,
        "service_fee_percentage": 15,
        "marketing_service_id": "mkt-1",
        "marketing_sub_service_ids": ["sub-1"],
    }
    data.update(overrides)
    return data


def _booking():
    return BookingRequest(
        id="BK-GENERIC",
        booking_kind="GENERIC",
        provider_id=None,
        service_id=None,
        requested_marketing_service_id="mkt-1",
        requested_marketing_sub_service_id="sub-1",
        requested_service_label_snapshot="Vanilles",
        requested_options=["extra-long"],
        client_contact={"name": "Awa", "email": "awa@example.com"},
        location="Toulouse",
        location_preference="domicile",
        desired_date="2026-02-01T10:00:00+00:00",
        hair_length="standard",
        general_adjustments=["extra-long"],
        meche=False,
        current_hair_picture="",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=900,
        provider_price_estimate_cents=None,
        chateau_rose_fee_cents=900,
        amount_due_now_cents=900,
        payment_status="AUTHORIZED",
        payment_auth_id="auth_1",
        status="WAITING_PROVIDER_ASSIGNMENT",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _deps(service=None):
    repo = InMemoryBookingRepository()
    repo.add(_booking())
    return repo, InMemoryProviderCatalog(
        {"provider-1": {"svc-1": service or _service()}},
        {"provider-1": {"Toulouse"}},
    ), InMemoryNotifier(), FixedClock(datetime(2026, 1, 2, tzinfo=timezone.utc))


def test_assign_compatible_provider_to_generic_booking():
    repo, catalog, notifier, clock = _deps()

    booking = assign_provider_to_booking.execute(
        booking_id="BK-GENERIC",
        provider_id="provider-1",
        service_id="svc-1",
        booking_repository=repo,
        provider_catalog=catalog,
        notifier=notifier,
        clock=clock,
    )

    assert booking.status == "SUBMITTED"
    assert booking.provider_id == "provider-1"
    assert booking.service_id == "svc-1"
    assert booking.booking_kind == "PROVIDER_SELECTED"
    assert booking.provider_price_estimate_cents == 12500
    assert booking.estimated_price_cents == 13400
    assert len(notifier.messages) == 2


def test_assign_provider_rejects_service_that_does_not_match_intent():
    repo, catalog, notifier, clock = _deps(_service(marketing_sub_service_ids=["other-sub"]))

    with pytest.raises(ValidationError, match="compatible"):
        assign_provider_to_booking.execute(
            booking_id="BK-GENERIC",
            provider_id="provider-1",
            service_id="svc-1",
            booking_repository=repo,
            provider_catalog=catalog,
            notifier=notifier,
            clock=clock,
        )

    assert repo.get("BK-GENERIC").provider_id is None


def test_manual_assignment_can_skip_service_intent_match_when_operator_accepts_clarification_risk():
    repo, catalog, notifier, clock = _deps(_service(marketing_sub_service_ids=["other-sub"]))

    booking = assign_provider_to_booking.execute(
        booking_id="BK-GENERIC",
        provider_id="provider-1",
        service_id="svc-1",
        booking_repository=repo,
        provider_catalog=catalog,
        notifier=notifier,
        clock=clock,
        enforce_service_intent_match=False,
    )

    assert booking.status == "SUBMITTED"
    assert booking.provider_id == "provider-1"


def test_manual_assignment_skips_unsupported_options_by_default_for_counter_proposal_risk():
    repo, catalog, notifier, clock = _deps(_service(general_adjustments={}))

    booking = assign_provider_to_booking.execute(
        booking_id="BK-GENERIC",
        provider_id="provider-1",
        service_id="svc-1",
        booking_repository=repo,
        provider_catalog=catalog,
        notifier=notifier,
        clock=clock,
    )

    assert booking.status == "SUBMITTED"
    assert booking.provider_price_estimate_cents == 10000
    assert booking.general_adjustments == ["extra-long"]


def test_manual_assignment_can_enforce_pricing_options_when_needed():
    repo, catalog, notifier, clock = _deps(_service(general_adjustments={}))

    with pytest.raises(ValidationError, match="General adjustment"):
        assign_provider_to_booking.execute(
            booking_id="BK-GENERIC",
            provider_id="provider-1",
            service_id="svc-1",
            booking_repository=repo,
            provider_catalog=catalog,
            notifier=notifier,
            clock=clock,
            enforce_pricing_options=True,
        )

    assert repo.get("BK-GENERIC").provider_id is None
