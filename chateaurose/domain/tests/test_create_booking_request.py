from datetime import datetime, timezone

from chateaurose.domain.use_cases import create_booking_request
from chateaurose.domain.tests.stubs.booking_repository import InMemoryBookingRepository
from chateaurose.domain.tests.stubs.clock import FixedClock
from chateaurose.domain.tests.stubs.notifier import InMemoryNotifier
from chateaurose.domain.tests.stubs.payment_gateway import InMemoryPaymentGateway
from chateaurose.domain.tests.stubs.provider_catalog import InMemoryProviderCatalog


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


def _deps(service=None):
    return {
        "booking_repository": InMemoryBookingRepository(),
        "provider_catalog": InMemoryProviderCatalog(
            {"provider-1": {"svc-1": service or _service()}},
            {"provider-1": {"Toulouse"}},
        ),
        "payment_gateway": InMemoryPaymentGateway(),
        "notifier": InMemoryNotifier(),
        "clock": FixedClock(datetime(2026, 1, 1, tzinfo=timezone.utc)),
    }


def test_create_provider_selected_booking_authorizes_service_fee_only():
    deps = _deps()

    booking = create_booking_request.execute(
        provider_id="provider-1",
        service_id="svc-1",
        client_contact={"name": "Awa", "email": "awa@example.com", "phone": "0600000000"},
        location="Toulouse",
        location_preference="domicile",
        desired_date="2026-02-01T10:00:00+00:00",
        hair_length="standard",
        general_adjustments=[],
        meche=False,
        current_hair_picture="",
        inspiration_pictures=[],
        free_text="",
        operations_email="ops@example.com",
        **deps,
    )

    assert booking.status == "SUBMITTED"
    assert booking.booking_kind == "PROVIDER_SELECTED"
    assert booking.provider_price_estimate_cents == 10000
    assert booking.chateau_rose_fee_cents == 1500
    assert booking.amount_due_now_cents == 1500
    assert booking.payment_status == "AUTHORIZED"
    assert deps["payment_gateway"].auth_calls[0]["amount_cents"] == 1500


def test_create_provider_selected_booking_sends_operations_copy():
    deps = _deps()

    booking = create_booking_request.execute(
        provider_id="provider-1",
        service_id="svc-1",
        client_contact={"name": "Awa", "email": "awa@example.com", "phone": "0600000000"},
        location="Toulouse",
        location_preference="domicile",
        desired_date="2026-02-01T10:00:00+00:00",
        hair_length="standard",
        general_adjustments=[],
        meche=False,
        current_hair_picture="",
        inspiration_pictures=[],
        free_text="",
        operations_email="ops@example.com",
        provider_booking_url_base="https://example.com/pro/bookings/",
        **deps,
    )

    assert [message["recipient"] for message in deps["notifier"].messages] == [
        "provider-1",
        "ops@example.com",
        "awa@example.com",
    ]
    operations_copy = deps["notifier"].messages[1]
    assert operations_copy["subject"] == f"Copie nouvelle demande · {booking.id}"
    assert operations_copy["reply_to"] == "awa@example.com"
    assert f"- ID demande : {booking.id}" in operations_copy["body"]
    assert "- Prestataire : provider-1" in operations_copy["body"]
    assert "https://example.com/pro/bookings/" in operations_copy["body"]
    provider_message = deps["notifier"].messages[0]
    assert "awa@example.com" not in provider_message["body"]
    assert "0600000000" not in provider_message["body"]
    assert all(message["subject"] != "Quelques infos avant de valider ton RDV" for message in deps["notifier"].messages)


def test_create_provider_selected_booking_with_waived_fee_skips_payment():
    deps = _deps()

    booking = create_booking_request.execute(
        provider_id="provider-1",
        service_id="svc-1",
        client_contact={"name": "Awa", "email": "awa@example.com"},
        location="Toulouse",
        location_preference="domicile",
        desired_date="2026-02-01T10:00:00+00:00",
        hair_length="standard",
        general_adjustments=[],
        meche=False,
        waive_service_fee=True,
        current_hair_picture="",
        inspiration_pictures=[],
        free_text="",
        **deps,
    )

    assert booking.status == "SUBMITTED"
    assert booking.amount_due_now_cents == 0
    assert booking.payment_status == "WAIVED"
    assert deps["payment_gateway"].auth_calls == []


def test_create_generic_booking_waits_for_provider_assignment():
    deps = _deps()

    booking = create_booking_request.execute(
        client_contact={"name": "Awa", "email": "awa@example.com", "phone": "0600000000"},
        requested_marketing_service_id="mkt-1",
        requested_marketing_sub_service_id="sub-1",
        requested_service_label_snapshot="Vanilles",
        chateau_rose_fee_cents=900,
        location="Toulouse",
        location_preference="domicile",
        desired_date="2026-02-01T10:00:00+00:00",
        hair_length="standard",
        requested_options=["extra-long"],
        meche=False,
        current_hair_picture="",
        inspiration_pictures=[],
        free_text="",
        operations_email="ops@example.com",
        **deps,
    )

    assert booking.status == "WAITING_PROVIDER_ASSIGNMENT"
    assert booking.booking_kind == "GENERIC"
    assert booking.provider_id is None
    assert booking.service_id is None
    assert booking.requested_options == ["extra-long"]
    assert booking.amount_due_now_cents == 900
    assert deps["payment_gateway"].auth_calls[0]["amount_cents"] == 900


def test_create_generic_booking_with_waived_fee_skips_payment():
    deps = _deps()

    booking = create_booking_request.execute(
        client_contact={"name": "Awa", "email": "awa@example.com", "phone": "0600000000"},
        requested_marketing_service_id="mkt-1",
        requested_service_label_snapshot="Vanilles",
        chateau_rose_fee_cents=0,
        location="À préciser",
        location_preference="salon",
        desired_date="Samedi après-midi",
        hair_length="standard",
        requested_options=[],
        meche=False,
        current_hair_picture="",
        inspiration_pictures=[],
        free_text="",
        operations_email="ops@example.com",
        **deps,
    )

    assert booking.status == "WAITING_PROVIDER_ASSIGNMENT"
    assert booking.amount_due_now_cents == 0
    assert booking.payment_status == "WAIVED"
    assert deps["payment_gateway"].auth_calls == []


def test_generic_booking_can_store_subservice_price_estimate():
    deps = _deps()

    booking = create_booking_request.execute(
        client_contact={"name": "Awa", "email": "awa@example.com"},
        requested_marketing_service_id="mkt-1",
        requested_marketing_sub_service_id="sub-1",
        requested_service_label_snapshot="Braids · Vanilles",
        requested_options=["long"],
        generic_provider_price_estimate_cents=12000,
        chateau_rose_fee_cents=1800,
        location="À préciser",
        location_preference="salon",
        desired_date="2026-02-01T10:00:00+00:00",
        hair_length="long",
        current_hair_picture="",
        inspiration_pictures=[],
        free_text="",
        **deps,
    )

    assert booking.booking_kind == "GENERIC"
    assert booking.provider_id is None
    assert booking.service_id is None
    assert booking.requested_marketing_sub_service_id == "sub-1"
    assert booking.status == "WAITING_PROVIDER_ASSIGNMENT"
    assert booking.provider_price_estimate_cents == 12000
    assert booking.chateau_rose_fee_cents == 1800
    assert booking.amount_due_now_cents == 1800
    assert booking.payment_status == "AUTHORIZED"
