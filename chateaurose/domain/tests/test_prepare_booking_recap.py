import pytest

from chateaurose.domain.exceptions import ValidationError
from chateaurose.domain.use_cases import prepare_booking_recap


def test_prepare_booking_recap_normalizes_payload():
    recap = prepare_booking_recap.execute(
        provider_id=12,
        service_id=44,
        service_name="Knotless braids",
        client_name=" Sarah ",
        client_email="sarah@example.com",
        desired_date_iso="2026-04-01T10:30:00+00:00",
        location_preference="domicile",
        location="Toulouse",
        client_address=" 10 rue du test ",
        hair_length="long",
        general_adjustments=[" extra", " ", "wash"],
        meche=True,
        free_text="  Merci  ",
        current_hair_picture="bookings/current/photo.jpg",
        inspiration_pictures=[" book1.jpg ", ""],
    )

    assert recap["provider_id"] == "12"
    assert recap["service_id"] == "44"
    assert recap["client_name"] == "Sarah"
    assert recap["client_address"] == "10 rue du test"
    assert recap["general_adjustments"] == ["extra", "wash"]
    assert recap["inspiration_pictures"] == ["book1.jpg"]
    assert recap["meche"] is True


def test_prepare_booking_recap_requires_address_for_domicile():
    with pytest.raises(ValidationError) as exc:
        prepare_booking_recap.execute(
            provider_id=12,
            service_id=44,
            service_name="Knotless braids",
            client_name="Sarah",
            client_email="sarah@example.com",
            desired_date_iso="2026-04-01T10:30:00+00:00",
            location_preference="domicile",
            location="Toulouse",
            client_address="",
            hair_length="long",
            general_adjustments=[],
            meche=False,
            free_text="",
            current_hair_picture="bookings/current/photo.jpg",
            inspiration_pictures=[],
        )

    assert str(exc.value) == "Missing required field: client_address"


def test_prepare_booking_recap_rejects_invalid_location_preference():
    with pytest.raises(ValidationError) as exc:
        prepare_booking_recap.execute(
            provider_id=12,
            service_id=44,
            service_name="Knotless braids",
            client_name="Sarah",
            client_email="sarah@example.com",
            desired_date_iso="2026-04-01T10:30:00+00:00",
            location_preference="unknown",
            location="Toulouse",
            client_address="10 rue du test",
            hair_length="long",
            general_adjustments=[],
            meche=False,
            free_text="",
            current_hair_picture="bookings/current/photo.jpg",
            inspiration_pictures=[],
        )

    assert str(exc.value) == "Invalid location_preference"
