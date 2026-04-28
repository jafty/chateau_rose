from pathlib import Path
import sys


def _ensure_project_root_on_path():
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_ensure_project_root_on_path()

from chateaurose.domain.services.pricing import compute_checkout_amounts_from_total_cents


def test_compute_checkout_amounts_from_total_cents_with_service_fee():
    amounts = compute_checkout_amounts_from_total_cents(
        total_cents=1150,
        deposit_percentage=30,
        service_fee_percentage=15,
    )

    assert amounts["subtotal_cents"] == 1000
    assert amounts["service_fee_cents"] == 150
    assert amounts["reservation_fee_cents"] == 450
    assert amounts["remaining_cents"] == 700


def test_compute_checkout_amounts_from_total_cents_without_service_fee():
    amounts = compute_checkout_amounts_from_total_cents(
        total_cents=1000,
        deposit_percentage=30,
        service_fee_percentage=0,
    )

    assert amounts["subtotal_cents"] == 1000
    assert amounts["service_fee_cents"] == 0
    assert amounts["reservation_fee_cents"] == 300
    assert amounts["remaining_cents"] == 700
