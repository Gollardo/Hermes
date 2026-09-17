from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.depreciation.calculation import inflation_target, schedule
from app.modules.depreciation.schemas import PurchaseCreate

D = Decimal


def test_compound_inflation_and_fractional_years_use_decimal() -> None:
    assert inflation_target(D("200000"), D("10"), 36) == D("266200.0000")
    assert inflation_target(D("100"), D("21"), 6) == D("110.0000")
    assert inflation_target(D("200000.1234"), D("0"), 36) == D("200000.1234")


def test_current_plan_is_fixed_until_month_ends() -> None:
    rows = schedule(D("266200"), "2026-08", 36, "2026-09", {"2026-09": D("5000")})
    assert rows[0]["planned"] == "7394.4444"
    assert rows[0]["remaining"] == "2394.4444"
    next_month = schedule(D("266200"), "2026-08", 36, "2026-10", {"2026-09": D("5000")})
    assert next_month[0]["state"] == "closed"
    assert next_month[1]["planned"] == "7462.8571"
    assert rows[1]["planned"] == next_month[1]["planned"]


def test_overpayment_and_missed_months() -> None:
    rows = schedule(D("200000"), "2026-08", 36, "2026-10", {"2026-09": D("10000")})
    assert rows[1]["planned"] == "5428.5714"
    missed = schedule(D("200000"), "2026-08", 36, "2026-12", {})
    assert missed[3]["planned"] == "6060.6060"


def test_rounding_closes_exactly_and_months_cross_year_and_leap_day() -> None:
    rows = schedule(D("100.0001"), "2027-12", 3, "2027-12", {})
    assert [r["month"] for r in rows] == ["2028-01", "2028-02", "2028-03"]
    assert sum((D(r["planned"]) for r in rows), D(0)) == D("100.0001")
    assert rows[-1]["planned"] == "33.3334"


def test_expiry_early_funding_and_release() -> None:
    assert schedule(D("100"), "2026-01", 1, "2026-03", {})[0]["state"] == "closed"
    rows = schedule(D("100"), "2026-01", 3, "2026-03", {"2026-02": D("100")})
    assert rows[1]["planned"] == "0.0000"
    rows = schedule(D("100"), "2026-01", 3, "2026-04", {"2026-02": D("100"), "2026-03": D("-20")})
    assert rows[2]["planned"] == "20.0000"
    rows = schedule(D("100"), "2026-01", 2, "2026-01", {"2026-01": D("20")})
    assert rows[0]["planned"] == "40.0000"


@pytest.mark.parametrize(
    "override",
    [
        {"cost": 10.5},
        {"cost": "NaN"},
        {"cost": "0"},
        {"inflation": "-1"},
        {"inflation": "101"},
        {"inflation": "0.00001"},
        {"months": 0},
        {"months": 601},
        {"months": 1.5},
        {"purchase_month": "2026-13"},
        {"purchase_month": "0000-01"},
        {"purchase_month": "9999-12"},
        {"name": "   "},
        {"cost": "9999999999999999.9999", "inflation": "100"},
    ],
)
def test_invalid_parameters(override: dict[str, object]) -> None:
    payload: dict[str, object] = dict(
        name="Laptop", cost="200000", inflation="10", months=36, purchase_month="2026-08"
    )
    payload.update(override)
    with pytest.raises(ValidationError):
        PurchaseCreate.model_validate(payload)
