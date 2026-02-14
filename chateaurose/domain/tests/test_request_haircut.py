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
                "general_adjustments": {"motif": 500},
                "meche_bonus_cents": 2000,
                "deposit_cents": 2000,
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
        location_preference="domicile",
        client_address="5 place du Capitole, 31000 Toulouse",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        general_adjustment="motif",
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
        provider_booking_url_base="https://example.com/espace_pro/demandes/",
    )

    assert request.status == request_haircut.SUBMITTED
    assert request.provider_id == provider_id
    assert request.service_id == service_id
    assert request.location == zone
    assert request.location_preference == "domicile"
    assert request.client_address == "5 place du Capitole, 31000 Toulouse"
    assert request.estimated_price_cents == 5000 + 1500 + 500 + 2000  # base + hair length adj + motif + mèche bonus
    assert request.payment_auth_id == "auth_1"
    assert request.created_at == now

    # Payment auth created for €20 deposit
    assert payment_gateway.auth_calls == [
        {"amount_cents": 2000, "currency": "EUR", "reference": request.id, "id": "auth_1"}
    ]

    # Provider and client notified immediately
    assert notifier.messages == [
        {
            "recipient": provider_id,
            "subject": "Nouvelle demande de coiffure",
            "body": "\n".join(
                [
                    "Bonne nouvelle ! Tu as une nouvelle demande de coiffure.",
                    "Client·e : Sarah (sarah@example.com)",
                    "Prestation : Tresses africaines",
                    "Date souhaitée : 2026-01-10T17:00:00Z",
                    "Lieu : Saint-Cyprien",
                    "Longueur : long",
                    "Mèches : oui",
                    f"ID demande : {request.id}",
                    "Message : Je suis dispo surtout les vendredis soir",
                    "",
                    "Pour répondre et proposer un créneau, ouvre la demande :",
                    f"https://example.com/espace_pro/demandes/{request.id}/",
                ]
            ),
        },
        {
            "recipient": "sarah@example.com",
            "subject": "Demande envoyée",
            "body": "\n".join(
                [
                    "Merci Sarah ! Ta demande pour Tresses africaines est bien envoyée.",
                    "On revient vers toi dès que la coiffeuse te propose un créneau.",
                    "",
                    "Récapitulatif :",
                    "- Prestation : Tresses africaines",
                    "- Date souhaitée : 2026-01-10T17:00:00Z",
                    "- Lieu : Saint-Cyprien",
                    "- Longueur : long",
                    "- Mèches : oui",
                    f"- ID demande : {request.id}",
                    "- Ton message : Je suis dispo surtout les vendredis soir",
                ]
            ),
        },
    ]




def test_request_haircut_adds_domicile_bonus_to_estimated_price():
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
                "hair_length_adjustments": {"long": 1000},
                "general_adjustments": {},
                "meche_bonus_cents": 0,
                "at_home_bonus_cents": 1200,
                "deposit_cents": 2000,
            }
        }
    }
    zones_by_provider = {provider_id: {zone}}

    provider_catalog = InMemoryProviderCatalog(
        services_by_provider=services_by_provider,
        zones_by_provider=zones_by_provider,
    )

    request = request_haircut.execute(
        provider_id=provider_id,
        service_id=service_id,
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location=zone,
        location_preference="domicile",
        client_address="5 place du Capitole, 31000 Toulouse",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=["s3://bucket/inspo1.jpg"],
        free_text="",
        booking_repository=InMemoryBookingRepository(),
        provider_catalog=provider_catalog,
        payment_gateway=InMemoryPaymentGateway(),
        notifier=InMemoryNotifier(),
        reminder_gateway=InMemoryReminderGateway(),
        clock=clock,
    )

    assert request.estimated_price_cents == 7200


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
                "deposit_cents": 2000,
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
        location_preference="domicile",
        client_address="5 place du Capitole, 31000 Toulouse",
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
            location_preference="domicile",
            client_address="5 place du Capitole, 31000 Toulouse",
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
                "deposit_cents": 2000,
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
        location_preference="domicile",
        client_address="5 place du Capitole, 31000 Toulouse",
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
                "deposit_cents": 2000,
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
            location_preference="domicile",
            client_address="5 place du Capitole, 31000 Toulouse",
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
                "deposit_cents": 2000,
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
        location="Paris 10e",
        location_preference="salon",
        provider_salon_zone="Paris 10e",
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

    assert request.location == "Paris 10e"


def test_request_haircut_requires_salon_zone_for_salon_booking():
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
                "hair_length_adjustments": {"long": 0},
                "meche_bonus_cents": 0,
                "deposit_cents": 2000,
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

    with pytest.raises(ValidationError):
        request_haircut.execute(
            provider_id=provider_id,
            service_id=service_id,
            client_contact={"name": "Sarah", "email": "sarah@example.com"},
            location="",
            location_preference="salon",
            provider_salon_zone="",
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


@pytest.mark.parametrize(
    "missing_field, payload",
    [
        ("client_name", {"client_contact": {"name": "", "email": "sarah@example.com"}}),
        ("client_email", {"client_contact": {"name": "Sarah", "email": ""}}),
        ("location", {"location": ""}),
        ("client_address", {"client_address": ""}),
        ("desired_date", {"desired_date": ""}),
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
                "deposit_cents": 2000,
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
        location_preference="domicile",
        client_address="5 place du Capitole, 31000 Toulouse",
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


def test_request_haircut_requires_length_when_multiple_adjustments():
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
                "deposit_cents": 2000,
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

    with pytest.raises(ValidationError) as exc:
        request_haircut.execute(
            provider_id=provider_id,
            service_id=service_id,
            client_contact={"name": "Sarah", "email": "sarah@example.com"},
            location=zone,
            location_preference="domicile",
            client_address="5 place du Capitole, 31000 Toulouse",
            desired_date="2026-01-10T17:00:00Z",
            hair_length="",
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

    assert "hair_length" in str(exc.value)
    assert booking_repository.saved == {}


def test_request_haircut_defaults_length_and_adjustment_when_single_option():
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
                "hair_length_adjustments": {},
                "general_adjustments": {},
                "deposit_cents": 2000,
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
        location_preference="domicile",
        client_address="5 place du Capitole, 31000 Toulouse",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="",
        general_adjustment="",
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

    assert booking.hair_length == "standard"
    assert booking.general_adjustment == "standard"
    assert booking.estimated_price_cents == 5000


def test_request_haircut_computes_deposit_from_percentage():
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
                "base_price_cents": 5100,
                "hair_length_adjustments": {"standard": 0},
                "general_adjustments": {"standard": 0},
                "deposit_percentage": 35,
            }
        }
    }

    provider_catalog = InMemoryProviderCatalog(
        services_by_provider=services_by_provider,
        zones_by_provider={provider_id: {zone}},
    )
    payment_gateway = InMemoryPaymentGateway()

    booking = request_haircut.execute(
        provider_id=provider_id,
        service_id=service_id,
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location=zone,
        location_preference="domicile",
        client_address="5 place du Capitole, 31000 Toulouse",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="standard",
        general_adjustment="standard",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        booking_repository=InMemoryBookingRepository(),
        provider_catalog=provider_catalog,
        payment_gateway=payment_gateway,
        notifier=InMemoryNotifier(),
        reminder_gateway=InMemoryReminderGateway(),
        clock=clock,
    )

    assert booking.estimated_price_cents == 5100
    assert payment_gateway.auth_calls[0]["amount_cents"] == 1785


def test_request_haircut_keeps_fixed_deposit_when_percentage_missing():
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
                "base_price_cents": 5100,
                "hair_length_adjustments": {"standard": 0},
                "general_adjustments": {"standard": 0},
                "deposit_cents": 2000,
            }
        }
    }

    provider_catalog = InMemoryProviderCatalog(
        services_by_provider=services_by_provider,
        zones_by_provider={provider_id: {zone}},
    )
    payment_gateway = InMemoryPaymentGateway()

    request_haircut.execute(
        provider_id=provider_id,
        service_id=service_id,
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location=zone,
        location_preference="domicile",
        client_address="5 place du Capitole, 31000 Toulouse",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="standard",
        general_adjustment="standard",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        booking_repository=InMemoryBookingRepository(),
        provider_catalog=provider_catalog,
        payment_gateway=payment_gateway,
        notifier=InMemoryNotifier(),
        reminder_gateway=InMemoryReminderGateway(),
        clock=clock,
    )

    assert payment_gateway.auth_calls[0]["amount_cents"] == 2000
