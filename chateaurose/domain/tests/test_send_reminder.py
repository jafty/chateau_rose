from datetime import datetime, timedelta, timezone

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.tests.stubs.booking_repository import InMemoryBookingRepository
from chateaurose.domain.tests.stubs.notifier import InMemoryNotifier
from chateaurose.domain.use_cases import send_reminder


def test_send_reminder_only_if_submitted_after_24h():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    now = created_at + timedelta(hours=24, minutes=1)

    booking = BookingRequest(
        id="booking_7",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "phone": "+33600000000"},
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche="not_provided",
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_7",
        status="SUBMITTED",
        created_at=created_at,
    )
    repo.add(booking)

    send_reminder.execute(
        booking_id="booking_7",
        now=now,
        booking_repository=repo,
        notifier=notifier,
    )

    assert notifier.messages == [
        {
            "recipient": "provider_1",
            "subject": "Rappel: demande en attente",
            "body": "Vous avez une demande en attente de réponse.",
        }
    ]


def test_no_reminder_if_not_submitted_or_before_24h():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    now = created_at + timedelta(hours=23)

    booking = BookingRequest(
        id="booking_8",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "phone": "+33600000000"},
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche="not_provided",
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_8",
        status="CONFIRMED",
        created_at=created_at,
    )
    repo.add(booking)

    send_reminder.execute(
        booking_id="booking_8",
        now=now,
        booking_repository=repo,
        notifier=notifier,
    )

    assert notifier.messages == []
