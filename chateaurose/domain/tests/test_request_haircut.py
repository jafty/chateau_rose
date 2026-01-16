from datetime import datetime, timezone

import pytest

from chateaurose.domain.exceptions import ValidationError

from chateaurose.domain.tests.stubs.booking_repository import InMemoryBookingRepository
from chateaurose.domain.tests.stubs.clock import FixedClock
from chateaurose.domain.tests.stubs.notifier import InMemoryNotifier
from chateaurose.domain.tests.stubs.payment_gateway import InMemoryPaymentGateway
from chateaurose.domain.tests.stubs.provider_catalog import InMemoryProviderCatalog
from chateaurose.domain.tests.stubs.reminder import InMemoryReminderGateway

# The implementation under test will live in chateaurose.domain.use_cases.request_haircut
from chateaurose.domain.use_cases import request_haircut


def test_request_haircut_submitted_with_auth_and_notification():
    now = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    clock = FixedClock(now)

    provider_id = "provider_1"
    service_id = "service_tresses"
    zone = "Saint-Cyprien"

    services_by_provider = {
        provider_id: {
            service_id: {
                "id": service_id,
                "name": "Tresses africaines",
                "base_price_cents": 5000,
                "hair_length_adjustments": {"long": 1500, "medium": 0, "short": -500},
                "meche_bonus_cents": 2000,
            }
        }
    }
    zones_by_provider = {provider_id: {zone}}

    provider_catalog = InMemoryProviderCatalog(
        services_by_provider=services_by_provider,
        zones_by_provider=zones_by_provider,
    )
    booking_repository = InMemoryBookingRepository()
    payment_gateway = InMemoryPaymentGateway()
    notifier = InMemoryNotifier()
    reminder_gateway = InMemoryReminderGateway()

    request = request_haircut.execute(
        provider_id=provider_id,
        service_id=service_id,
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location=zone,
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=True,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=["s3://bucket/inspo1.jpg"],
        free_text="Je suis dispo surtout les vendredis soir",
        booking_repository=booking_repository,
        provider_catalog=provider_catalog,
        payment_gateway=payment_gateway,
        notifier=notifier,
        reminder_gateway=reminder_gateway,
        clock=clock,
    )

    assert request.status == request_haircut.SUBMITTED
    assert request.provider_id == provider_id
    assert request.service_id == service_id
    assert request.location == zone
    assert request.estimated_price_cents == 5000 + 1500 + 2000  # base + hair length adj + mèche bonus
    assert request.payment_auth_id == "auth_1"
    assert request.created_at == now

    # Payment auth created for €10
    assert payment_gateway.auth_calls == [
        {"amount_cents": 1000, "currency": "EUR", "reference": request.id, "id": "auth_1"}
    ]

    # Provider and client notified immediately
    assert notifier.messages == [
        {
            "recipient": provider_id,
            "subject": "Nouvelle demande de coiffure",
            "body": "Sarah veut prendre rendez-vous avec vous.",
        },
        {
            "recipient": "sarah@example.com",
            "subject": "Demande envoyée",
            "body": f"{provider_id} a bien reçu votre demande. Vous recevrez un message lorsque le rendez-vous sera confirmé.",
        },
    ]


def test_request_haircut_generates_readable_id():
    now = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    clock = FixedClock(now)

    provider_id = "provider_1"
    service_id = "service_tresses"
    zone = "Saint-Cyprien"

    services_by_provider = {
        provider_id: {
            service_id: {
                "id": service_id,
                "name": "Tresses africaines",
                "base_price_cents": 5000,
                "hair_length_adjustments": {"long": 1500, "medium": 0, "short": -500},
                "meche_bonus_cents": 2000,
            }
        }
    }
    zones_by_provider = {provider_id: {zone}}

    provider_catalog = InMemoryProviderCatalog(
        services_by_provider=services_by_provider,
        zones_by_provider=zones_by_provider,
    )
    booking_repository = InMemoryBookingRepository()
    payment_gateway = InMemoryPaymentGateway()
    notifier = InMemoryNotifier()
    reminder_gateway = InMemoryReminderGateway()

    booking = request_haircut.execute(
        provider_id=provider_id,
        service_id=service_id,
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location=zone,
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=True,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=["s3://bucket/inspo1.jpg"],
        free_text="",
        booking_repository=booking_repository,
        provider_catalog=provider_catalog,
        payment_gateway=payment_gateway,
        notifier=notifier,
        reminder_gateway=reminder_gateway,
        clock=clock,
    )

    assert booking.id.startswith("BK-")
    readable_part = booking.id.split("BK-")[-1]
    assert len(readable_part) == 8
    assert readable_part.isalnum()


def test_request_haircut_rejects_service_not_offered():
    now = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    clock = FixedClock(now)

    provider_id = "provider_1"
    service_id = "service_not_offered"
    zone = "Saint-Cyprien"

    services_by_provider = {provider_id: {}}
    zones_by_provider = {provider_id: {zone}}

    provider_catalog = InMemoryProviderCatalog(
        services_by_provider=services_by_provider,
        zones_by_provider=zones_by_provider,
    )
    booking_repository = InMemoryBookingRepository()
    payment_gateway = InMemoryPaymentGateway()
    notifier = InMemoryNotifier()
    reminder_gateway = InMemoryReminderGateway()

    with pytest.raises(ValidationError):
        request_haircut.execute(
            provider_id=provider_id,
            service_id=service_id,
            client_contact={"name": "Sarah", "email": "sarah@example.com"},
            location=zone,
            desired_date="2026-01-10T17:00:00Z",
            hair_length="long",
            meche=True,
            current_hair_picture="s3://bucket/hair.jpg",
            inspiration_pictures=[],
            free_text="",
            booking_repository=booking_repository,
            provider_catalog=provider_catalog,
            payment_gateway=payment_gateway,
            notifier=notifier,
            reminder_gateway=reminder_gateway,
            clock=clock,
        )

    assert booking_repository.saved == {}
    assert payment_gateway.auth_calls == []
    assert notifier.messages == []
    assert reminder_gateway.reminders == []


def test_request_haircut_estimated_price_defaults_to_base_when_no_adjustments():
    now = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    clock = FixedClock(now)

    provider_id = "provider_1"
    service_id = "service_tresses"
    zone = "Saint-Cyprien"

    services_by_provider = {
        provider_id: {
            service_id: {
                "id": service_id,
                "name": "Tresses africaines",
                "base_price_cents": 5000,
                "hair_length_adjustments": {"long": 1500, "medium": 0},
                "meche_bonus_cents": 2000,
            }
        }
    }
    zones_by_provider = {provider_id: {zone}}

    provider_catalog = InMemoryProviderCatalog(
        services_by_provider=services_by_provider,
        zones_by_provider=zones_by_provider,
    )
    booking_repository = InMemoryBookingRepository()
    payment_gateway = InMemoryPaymentGateway()
    notifier = InMemoryNotifier()
    reminder_gateway = InMemoryReminderGateway()

    request = request_haircut.execute(
        provider_id=provider_id,
        service_id=service_id,
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location=zone,
        desired_date="2026-01-10T17:00:00Z",
        hair_length="medium",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        booking_repository=booking_repository,
        provider_catalog=provider_catalog,
        payment_gateway=payment_gateway,
        notifier=notifier,
        reminder_gateway=reminder_gateway,
        clock=clock,
    )

    assert request.estimated_price_cents == 5000


def test_request_haircut_rejects_zone_not_covered():
    now = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    clock = FixedClock(now)

    provider_id = "provider_1"
    service_id = "service_tresses"

    services_by_provider = {
        provider_id: {
            service_id: {
                "id": service_id,
                "name": "Tresses africaines",
                "base_price_cents": 5000,
                "hair_length_adjustments": {"medium": 0},
                "meche_bonus_cents": 0,
            }
        }
    }
    zones_by_provider = {provider_id: {"Zone A"}}

    provider_catalog = InMemoryProviderCatalog(
        services_by_provider=services_by_provider,
        zones_by_provider=zones_by_provider,
    )
    booking_repository = InMemoryBookingRepository()
    payment_gateway = InMemoryPaymentGateway()
    notifier = InMemoryNotifier()
    reminder_gateway = InMemoryReminderGateway()

    with pytest.raises(ValidationError):
        request_haircut.execute(
            provider_id=provider_id,
            service_id=service_id,
            client_contact={"name": "Sarah", "email": "sarah@example.com"},
            location="OutOfZone",
            desired_date="2026-01-10T17:00:00Z",
            hair_length="medium",
            meche=True,
            current_hair_picture="s3://bucket/hair.jpg",
            inspiration_pictures=[],
            free_text="",
            booking_repository=booking_repository,
            provider_catalog=provider_catalog,
            payment_gateway=payment_gateway,
            notifier=notifier,
            reminder_gateway=reminder_gateway,
            clock=clock,
        )

    assert booking_repository.saved == {}
    assert payment_gateway.auth_calls == []
    assert notifier.messages == []
    assert reminder_gateway.reminders == []


def test_salon_only_provider_allows_salon_location_without_zones():
    now = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    clock = FixedClock(now)

    provider_id = "provider_1"
    service_id = "service_tresses"

    services_by_provider = {
        provider_id: {
            service_id: {
                "id": service_id,
                "name": "Tresses africaines",
                "base_price_cents": 5000,
                "hair_length_adjustments": {"long": 1500, "medium": 0, "short": -500},
                "meche_bonus_cents": 2000,
            }
        }
    }
    zones_by_provider = {provider_id: set()}
    location_modes = {provider_id: InMemoryProviderCatalog.LOCATION_MODE_SALON_ONLY}

    provider_catalog = InMemoryProviderCatalog(
        services_by_provider=services_by_provider,
        zones_by_provider=zones_by_provider,
        location_modes=location_modes,
    )
    booking_repository = InMemoryBookingRepository()
    payment_gateway = InMemoryPaymentGateway()
    notifier = InMemoryNotifier()
    reminder_gateway = InMemoryReminderGateway()

    request = request_haircut.execute(
        provider_id=provider_id,
        service_id=service_id,
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location=InMemoryProviderCatalog.SALON_LOCATION_LABEL,
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        booking_repository=booking_repository,
        provider_catalog=provider_catalog,
        payment_gateway=payment_gateway,
        notifier=notifier,
        reminder_gateway=reminder_gateway,
        clock=clock,
    )

    assert request.location == InMemoryProviderCatalog.SALON_LOCATION_LABEL


@pytest.mark.parametrize(
    "missing_field, payload",
    [
        ("client_name", {"client_contact": {"name": "", "email": "sarah@example.com"}}),
        ("client_email", {"client_contact": {"name": "Sarah", "email": ""}}),
        ("location", {"location": ""}),
        ("desired_date", {"desired_date": ""}),
        ("hair_length", {"hair_length": ""}),
        ("meche", {"meche": None}),
        ("current_hair_picture", {"current_hair_picture": ""}),
    ],
)
def test_request_haircut_missing_mandatory_fields(missing_field, payload):
    now = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    clock = FixedClock(now)

    provider_id = "provider_1"
    service_id = "service_tresses"
    zone = "Saint-Cyprien"

    services_by_provider = {
        provider_id: {
            service_id: {
                "id": service_id,
                "name": "Tresses africaines",
                "base_price_cents": 5000,
            }
        }
    }
    zones_by_provider = {provider_id: {zone}}

    provider_catalog = InMemoryProviderCatalog(
        services_by_provider=services_by_provider,
        zones_by_provider=zones_by_provider,
    )
    booking_repository = InMemoryBookingRepository()
    payment_gateway = InMemoryPaymentGateway()
    notifier = InMemoryNotifier()
    reminder_gateway = InMemoryReminderGateway()

    base_kwargs = dict(
        provider_id=provider_id,
        service_id=service_id,
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location=zone,
        desired_date="2026-01-10T17:00:00Z",
        hair_length="medium",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        booking_repository=booking_repository,
        provider_catalog=provider_catalog,
        payment_gateway=payment_gateway,
        notifier=notifier,
        reminder_gateway=reminder_gateway,
        clock=clock,
    )
    base_kwargs.update(payload)

    with pytest.raises(ValidationError) as exc:
        request_haircut.execute(**base_kwargs)

    assert missing_field in str(exc.value)
    assert booking_repository.saved == {}
    assert payment_gateway.auth_calls == []
    assert notifier.messages == []
    assert reminder_gateway.reminders == []
