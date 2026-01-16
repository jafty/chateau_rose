from datetime import datetime, timezone

import pytest

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import InvalidState, PermissionError
from chateaurose.domain.tests.stubs.booking_repository import InMemoryBookingRepository
from chateaurose.domain.tests.stubs.notifier import InMemoryNotifier
from chateaurose.domain.tests.stubs.provider_catalog import InMemoryProviderCatalog
from chateaurose.domain.use_cases import update_proposal


def test_provider_proposes_update_moves_to_pending_client_validation_and_notifies_client():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()

    provider_id = "provider_1"
    client = {"name": "Sarah", "email": "sarah@example.com"}
    booking = BookingRequest(
        id="booking_1",
        provider_id=provider_id,
        service_id="service_tresses",
        client_contact=client,
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_1",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    updated = update_proposal.execute(
        booking_id="booking_1",
        provider_id=provider_id,
        new_price_cents=9000,
        new_date="2026-01-11T18:00:00Z",
        booking_repository=repo,
        notifier=notifier,
    )

    assert updated.status == update_proposal.PENDING_CLIENT_VALIDATION
    assert updated.proposed_price_cents == 9000
    assert updated.proposed_date == "2026-01-11T18:00:00Z"

    assert notifier.messages == [
        {
            "recipient": client["email"],
            "subject": "Proposition de rendez-vous",
            "body": "Une nouvelle proposition est disponible pour votre demande.",
        }
    ]


def test_update_proposal_rejects_wrong_provider():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()

    booking = BookingRequest(
        id="booking_2",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_2",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    with pytest.raises(PermissionError):
        update_proposal.execute(
            booking_id="booking_2",
            provider_id="intruder",
            new_price_cents=9000,
            new_date="2026-01-11T18:00:00Z",
            booking_repository=repo,
            notifier=notifier,
        )

    assert booking.status == "SUBMITTED"
    assert notifier.messages == []


def test_update_proposal_rejects_terminal_state():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()

    booking = BookingRequest(
        id="booking_3",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_3",
        status="CONFIRMED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    with pytest.raises(InvalidState):
        update_proposal.execute(
            booking_id="booking_3",
            provider_id="provider_1",
            new_price_cents=9000,
            new_date="2026-01-11T18:00:00Z",
            booking_repository=repo,
            notifier=notifier,
        )

    assert notifier.messages == []


def test_provider_can_send_multiple_proposals_before_terminal():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()

    provider_id = "provider_1"
    client = {"name": "Sarah", "email": "sarah@example.com"}
    booking = BookingRequest(
        id="booking_multi",
        provider_id=provider_id,
        service_id="service_tresses",
        client_contact=client,
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_multi",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    first = update_proposal.execute(
        booking_id="booking_multi",
        provider_id=provider_id,
        new_price_cents=9000,
        new_date="2026-01-11T18:00:00Z",
        booking_repository=repo,
        notifier=notifier,
    )
    second = update_proposal.execute(
        booking_id="booking_multi",
        provider_id=provider_id,
        new_price_cents=9500,
        new_date="2026-01-12T19:00:00Z",
        booking_repository=repo,
        notifier=notifier,
    )

    assert second.status == update_proposal.PENDING_CLIENT_VALIDATION
    assert second.proposed_price_cents == 9500
    assert second.proposed_date == "2026-01-12T19:00:00Z"
    # two notifications, one per proposal
    assert len(notifier.messages) == 2
