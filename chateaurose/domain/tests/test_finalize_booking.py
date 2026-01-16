from datetime import datetime, timedelta, timezone

import pytest

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.tests.stubs.booking_repository import InMemoryBookingRepository
from chateaurose.domain.tests.stubs.notifier import InMemoryNotifier
from chateaurose.domain.tests.stubs.payment_gateway import InMemoryPaymentGateway
from chateaurose.domain.use_cases import finalize_booking


def test_provider_confirms_original_captures_and_notifies():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

    booking = BookingRequest(
        id="booking_1",
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
        payment_auth_id="auth_1",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    updated = finalize_booking.execute(
        booking_id="booking_1",
        actor="provider",
        decision="confirm",
        now=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
    )

    assert updated.status == finalize_booking.CONFIRMED
    assert payments.capture_calls == [{"auth_id": "auth_1"}]
    assert notifier.messages == [
        {
            "recipient": "provider_1",
            "subject": "Rendez-vous confirmé",
            "body": "Vous avez confirmé le rendez-vous.",
        },
        {
            "recipient": "sarah@example.com",
            "subject": "Rendez-vous confirmé",
            "body": "Votre rendez-vous est confirmé.",
        },
    ]


def test_provider_rejects_releases_and_notifies():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

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

    updated = finalize_booking.execute(
        booking_id="booking_2",
        actor="provider",
        decision="reject",
        now=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
    )

    assert updated.status == finalize_booking.CANCELLED
    assert payments.release_calls == [{"auth_id": "auth_2"}]
    assert notifier.messages[-2:] == [
        {
            "recipient": "provider_1",
            "subject": "Demande annulée",
            "body": "Vous avez annulé la demande.",
        },
        {
            "recipient": "sarah@example.com",
            "subject": "Demande annulée",
            "body": "Votre demande a été refusée.",
        },
    ]


def test_client_accepts_proposal_captures_and_confirms():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

    booking = BookingRequest(
        id="booking_3",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        desired_date="2026-01-11T18:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_3",
        status="PENDING_CLIENT_VALIDATION",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
        proposed_price_cents=9000,
        proposed_date="2026-01-11T18:00:00Z",
    )
    repo.add(booking)

    updated = finalize_booking.execute(
        booking_id="booking_3",
        actor="client",
        decision="accept",
        now=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
    )

    assert updated.status == finalize_booking.CONFIRMED
    assert payments.capture_calls == [{"auth_id": "auth_3"}]


def test_client_refuses_proposal_releases_and_cancels():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

    booking = BookingRequest(
        id="booking_4",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        desired_date="2026-01-11T18:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_4",
        status="PENDING_CLIENT_VALIDATION",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
        proposed_price_cents=9000,
        proposed_date="2026-01-11T18:00:00Z",
    )
    repo.add(booking)

    updated = finalize_booking.execute(
        booking_id="booking_4",
        actor="client",
        decision="refuse",
        now=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
    )

    assert updated.status == finalize_booking.CANCELLED
    assert payments.release_calls == [{"auth_id": "auth_4"}]


def test_finalize_booking_rejects_invalid_actor():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

    booking = BookingRequest(
        id="booking_invalid_actor",
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
        payment_auth_id="auth_invalid_actor",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    with pytest.raises(finalize_booking.InvalidState):
        finalize_booking.execute(
            booking_id="booking_invalid_actor",
            actor="hacker",
        decision="confirm",
        now=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
    )

    assert booking.status == "SUBMITTED"
    assert payments.capture_calls == []
    assert payments.release_calls == []


def test_finalize_booking_idempotent_no_double_capture_or_release():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

    booking = BookingRequest(
        id="booking_idem",
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
        payment_auth_id="auth_idem",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    first = finalize_booking.execute(
        booking_id="booking_idem",
        actor="provider",
        decision="confirm",
        now=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
    )
    second = finalize_booking.execute(
        booking_id="booking_idem",
        actor="provider",
        decision="confirm",
        now=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
    )

    assert first.status == finalize_booking.CONFIRMED
    assert second.status == finalize_booking.CONFIRMED
    assert payments.capture_calls == [{"auth_id": "auth_idem"}]
    assert payments.release_calls == []


def test_finalize_booking_rejects_if_expired():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    booking = BookingRequest(
        id="booking_expired",
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
        payment_auth_id="auth_expired",
        status="SUBMITTED",
        created_at=created_at,
    )
    repo.add(booking)

    with pytest.raises(finalize_booking.InvalidState):
        finalize_booking.execute(
            booking_id="booking_expired",
            actor="provider",
            decision="confirm",
            now=created_at + timedelta(hours=49),
            booking_repository=repo,
            payment_gateway=payments,
            notifier=notifier,
        )

    assert payments.capture_calls == []
    assert payments.release_calls == []
