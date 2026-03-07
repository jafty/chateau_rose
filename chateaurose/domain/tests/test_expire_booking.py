from datetime import datetime, timedelta, timezone

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.tests.stubs.booking_repository import InMemoryBookingRepository
from chateaurose.domain.tests.stubs.notifier import InMemoryNotifier
from chateaurose.domain.tests.stubs.payment_gateway import InMemoryPaymentGateway
from chateaurose.domain.use_cases import expire_booking


def test_expire_booking_after_72h_releases_and_notifies():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    now = created_at + timedelta(hours=73)

    booking = BookingRequest(
        id="booking_5",
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
        payment_auth_id="auth_5",
        status="SUBMITTED",
        created_at=created_at,
    )
    repo.add(booking)

    expired = expire_booking.execute(
        booking_id="booking_5",
        now=now,
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
    )

    assert expired.status == expire_booking.CANCELLED
    assert payments.release_calls == [{"auth_id": "auth_5"}]
    assert notifier.messages == [
        {
            "recipient": "provider_1",
            "subject": "Demande expirée",
            "body": "\n".join(
                [
                    "Bonjour,",
                    "",
                    "La demande a expiré faute de confirmation.",
                    "Récapitulatif :",
                    "- Date : 2026-01-10T17:00:00Z",
                    "- Lieu : Saint-Cyprien",
                    "- Tarif : 85,00 €",
                    "",
                    "À bientôt,",
                    "L'équipe Château Rose",
                ]
            ),
        },
        {
            "recipient": "sarah@example.com",
            "subject": "Demande expirée",
            "body": "\n".join(
                [
                    "Bonjour Sarah,",
                    "",
                    "La demande a expiré faute de confirmation.",
                    "Récapitulatif :",
                    "- Date : 2026-01-10T17:00:00Z",
                    "- Lieu : Saint-Cyprien",
                    "- Tarif : 85,00 €",
                    "",
                    "Si tu veux, tu peux déposer une nouvelle demande.",
                    "À bientôt,",
                    "L'équipe Château Rose",
                ]
            ),
        },
    ]


def test_not_expired_before_72h():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    now = created_at + timedelta(hours=24)

    booking = BookingRequest(
        id="booking_6",
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
        payment_auth_id="auth_6",
        status="SUBMITTED",
        created_at=created_at,
    )
    repo.add(booking)

    still_open = expire_booking.execute(
        booking_id="booking_6",
        now=now,
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
    )

    assert still_open.status == "SUBMITTED"
    assert payments.release_calls == []
    assert notifier.messages == []
