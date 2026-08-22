import pytest

from chateaurose.domain.exceptions import ValidationError
from chateaurose.domain.services.pricing import (
    NOCTURNAL_SUPPLEMENT_CENTS,
    ceil_price_for_display_cents,
    compute_checkout_amounts_cents,
    floor_price_for_display_cents,
    estimate_service_price_cents,
    is_nocturnal_appointment,
)


@pytest.mark.parametrize(
    ("desired_at", "expected"),
    [(None, False), ("2026-08-22T19:59", False), ("2026-08-22T20:00", False),
     ("2026-08-22T20:01", True), ("not-a-date", False)],
)
def test_is_nocturnal_appointment_covers_boundary_and_invalid_values(desired_at, expected):
    assert is_nocturnal_appointment(desired_at) is expected


def test_estimate_service_price_adds_global_nocturnal_supplement_after_20h():
    price, _, _ = estimate_service_price_cents(
        service={"base_price_cents": 5000}, hair_length=None, general_adjustments=None,
        meche=False, location_preference="salon", desired_at="2026-08-22T20:30",
    )
    assert price == 5000 + NOCTURNAL_SUPPLEMENT_CENTS


def test_estimate_service_price_does_not_add_supplement_at_20h_exactly():
    price, _, _ = estimate_service_price_cents(
        service={"base_price_cents": 5000}, hair_length=None, general_adjustments=None,
        meche=False, location_preference="salon", desired_at="2026-08-22T20:00",
    )
    assert price == 5000


def test_estimate_service_price_includes_multiple_general_adjustments_and_domicile_bonus():
    service = {
        "base_price_cents": 5000,
        "hair_length_adjustments": {"short": 0, "long": 1500},
        "general_adjustments": {"motif": 400, "perle": 600},
        "meche_bonus_cents": 700,
        "at_home_bonus_cents": 1200,
    }

    estimated, normalized_length, normalized_adjustments = estimate_service_price_cents(
        service=service,
        hair_length="long",
        general_adjustments=["motif", "perle"],
        meche=True,
        location_preference="domicile",
    )

    assert estimated == 9400
    assert normalized_length == "long"
    assert normalized_adjustments == ["motif", "perle"]


def test_estimate_service_price_ignores_domicile_bonus_for_salon_choice():
    service = {
        "base_price_cents": 5000,
        "hair_length_adjustments": {"standard": 0},
        "general_adjustments": {},
        "meche_bonus_cents": 0,
        "at_home_bonus_cents": 1200,
    }

    estimated, normalized_length, normalized_adjustments = estimate_service_price_cents(
        service=service,
        hair_length=None,
        general_adjustments=None,
        meche=False,
        location_preference="salon",
    )

    assert estimated == 5000
    assert normalized_length == "standard"
    assert normalized_adjustments == []


def test_estimate_service_price_requires_supported_hair_length():
    service = {
        "base_price_cents": 5000,
        "hair_length_adjustments": {"short": 0, "long": 1500},
    }

    with pytest.raises(ValidationError, match="Hair length is not supported"):
        estimate_service_price_cents(
            service=service,
            hair_length="medium",
            general_adjustments=None,
            meche=False,
            location_preference="domicile",
        )


def test_estimate_service_price_requires_supported_general_adjustments():
    service = {
        "base_price_cents": 5000,
        "hair_length_adjustments": {"standard": 0},
        "general_adjustments": {"motif": 200},
    }

    with pytest.raises(ValidationError, match="General adjustment is not supported"):
        estimate_service_price_cents(
            service=service,
            hair_length="standard",
            general_adjustments=["premium"],
            meche=False,
            location_preference="domicile",
        )


def test_compute_checkout_amounts_includes_service_fee_in_total_and_reservation_fee():
    amounts = compute_checkout_amounts_cents(
        subtotal_cents=10000,
        deposit_percentage=30,
        service_fee_percentage=15,
    )

    assert amounts["deposit_cents"] == 3000
    assert amounts["service_fee_cents"] == 1500
    assert amounts["total_cents"] == 11500
    assert amounts["reservation_fee_cents"] == 4500
    assert amounts["remaining_cents"] == 7000


def test_compute_checkout_amounts_can_waive_service_fee():
    amounts = compute_checkout_amounts_cents(
        subtotal_cents=10000,
        deposit_percentage=30,
        service_fee_percentage=15,
        waive_service_fee=True,
    )

    assert amounts["service_fee_cents"] == 0
    assert amounts["total_cents"] == 10000
    assert amounts["reservation_fee_cents"] == 3000
    assert amounts["remaining_cents"] == 7000


def test_ceil_price_for_display_cents_rounds_up_to_next_full_euro():
    assert ceil_price_for_display_cents(11000) == 11000
    assert ceil_price_for_display_cents(11001) == 11100
    assert ceil_price_for_display_cents(11099) == 11100


def test_ceil_price_for_display_cents_handles_non_positive_values():
    assert ceil_price_for_display_cents(0) == 0
    assert ceil_price_for_display_cents(-50) == 0


def test_floor_price_for_display_cents_rounds_down_to_full_euro():
    assert floor_price_for_display_cents(11099) == 11000
    assert floor_price_for_display_cents(11000) == 11000


def test_floor_price_for_display_cents_handles_non_positive_values():
    assert floor_price_for_display_cents(0) == 0
    assert floor_price_for_display_cents(-50) == 0


def test_estimate_service_price_applies_one_required_type_adjustment():
    price, length, options = estimate_service_price_cents(
        service={
            "base_price_cents": 5000,
            "hair_length_adjustments": {"standard": 0},
            "type_adjustments": {"standard": 0, "premium": 1200},
            "general_adjustments": {},
        },
        hair_length="standard",
        type_adjustment="premium",
        general_adjustments=[],
        meche=False,
        location_preference="salon",
    )

    assert price == 6200
    assert length == "standard"
    assert options == []


def test_estimate_service_price_forces_standard_type_when_type_list_is_empty():
    price, _, _ = estimate_service_price_cents(
        service={
            "base_price_cents": 5000,
            "hair_length_adjustments": {},
            "type_adjustments": {},
        },
        hair_length=None,
        type_adjustment=None,
        general_adjustments=None,
        meche=False,
        location_preference="salon",
    )

    assert price == 5000


def test_estimate_service_price_rejects_an_unsupported_type():
    with pytest.raises(ValidationError, match="Type is not supported"):
        estimate_service_price_cents(
            service={
                "base_price_cents": 5000,
                "hair_length_adjustments": {"standard": 0},
                "type_adjustments": {"classique": 0, "premium": 1200},
            },
            hair_length="standard",
            type_adjustment="standard",
            general_adjustments=[],
            meche=False,
            location_preference="salon",
        )


def test_estimate_service_price_combines_type_with_all_other_adjustments():
    price, _, _ = estimate_service_price_cents(
        service={
            "base_price_cents": 5000,
            "hair_length_adjustments": {"long": 1000},
            "type_adjustments": {"premium": 1200},
            "general_adjustments": {"perles": 300},
            "meche_bonus_cents": 700,
            "at_home_bonus_cents": 800,
        },
        hair_length="long",
        type_adjustment="premium",
        general_adjustments=["perles"],
        meche=True,
        location_preference="domicile",
    )

    assert price == 9000
