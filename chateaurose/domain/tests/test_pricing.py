import pytest

from chateaurose.domain.exceptions import ValidationError
from chateaurose.domain.services.pricing import (
    compute_checkout_amounts_cents,
    estimate_service_price_cents,
)


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
