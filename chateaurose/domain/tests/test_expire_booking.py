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


def test_awaiting_alternative_uses_alternative_requested_at_for_expiry_window():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    alternative_requested_at = created_at + timedelta(hours=70)
    now = created_at + timedelta(hours=73)

    booking = BookingRequest(
        id="booking_alt_fresh",
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
        payment_auth_id="auth_alt_fresh",
        status=expire_booking.AWAITING_ALTERNATIVE_PROVIDER,
        created_at=created_at,
        alternative_requested_at=alternative_requested_at,
    )
    repo.add(booking)

    still_open = expire_booking.execute(
        booking_id="booking_alt_fresh",
        now=now,
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
    )

    assert still_open.status == expire_booking.AWAITING_ALTERNATIVE_PROVIDER
    assert payments.release_calls == []
    assert notifier.messages == []


def test_awaiting_alternative_expires_after_extended_window_and_releases_payment():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    alternative_requested_at = created_at + timedelta(hours=4)
    now = alternative_requested_at + timedelta(hours=73)

    booking = BookingRequest(
        id="booking_alt_expired",
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
        payment_auth_id="auth_alt_expired",
        status=expire_booking.AWAITING_ALTERNATIVE_PROVIDER,
        created_at=created_at,
        alternative_requested_at=alternative_requested_at,
    )
    repo.add(booking)

    expired = expire_booking.execute(
        booking_id="booking_alt_expired",
        now=now,
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
    )

    assert expired.status == expire_booking.CANCELLED
    assert payments.release_calls == [{"auth_id": "auth_alt_expired"}]
    assert notifier.messages[1]["recipient"] == "sarah@example.com"
    assert "Nous n'avons pas trouvé d'alternative compatible" in notifier.messages[1]["body"]
    assert "Ton empreinte bancaire a été libérée" in notifier.messages[1]["body"]


def test_expire_booking_notifies_operations_when_configured():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    booking = BookingRequest(
        id="booking_expire_ops",
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
        payment_auth_id="auth_expire_ops",
        status="SUBMITTED",
        created_at=created_at,
    )
    repo.add(booking)

    expire_booking.execute(
        booking_id="booking_expire_ops",
        now=created_at + timedelta(hours=73),
        booking_repository=repo,
        payment_gateway=payments,
        notifier=notifier,
        operations_email="ops@example.com",
    )

    assert notifier.messages[-1]["recipient"] == "ops@example.com"
    assert notifier.messages[-1]["subject"] == "Demande expirée · booking_expire_ops"
    assert notifier.messages[-1]["reply_to"] == "sarah@example.com"
