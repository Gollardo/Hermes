from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.modules.accounts.contracts import AccountIdentity
from app.modules.forecasting.contracts import ForecastHorizon, ProjectionSnapshot, project_snapshot
from app.modules.funds.contracts import FundResponse
from app.modules.operations.contracts import OperationType
from app.modules.scenarios.schemas import ScenarioRequest
from app.modules.scenarios.service import ScenarioError, assess_risk, compare
from app.modules.scenarios.snapshot import fingerprint
from app.modules.scheduling.contracts import OccurrenceStatus, PlannedOccurrence
from app.modules.settings.contracts import FundAllocationMode

TODAY = date(2026, 1, 31)
A, B = UUID(int=1), UUID(int=2)


def event(
    identity: int,
    amount: str,
    day: int = 1,
    kind: OperationType = OperationType.EXPENSE,
    allocate: bool = False,
) -> PlannedOccurrence:
    return PlannedOccurrence(
        id=UUID(int=identity),
        rule_id=None,
        due_on=TODAY + timedelta(days=day),
        type=kind,
        amount=Decimal(amount),
        description=f"Plan {identity}",
        account_id=A,
        destination_account_id=B if kind == OperationType.TRANSFER else None,
        allocate_to_funds=allocate,
        status=OccurrenceStatus.PENDING,
    )


def snapshot(events: tuple[PlannedOccurrence, ...] = ()) -> ProjectionSnapshot:
    return ProjectionSnapshot(
        today=TODAY,
        through_on=date(2027, 1, 31),
        currency="RUB",
        accounts=(AccountIdentity(A, "Main", False), AccountIdentity(B, "Savings", False)),
        balances=((A, Decimal("100.0001")), (B, Decimal(0))),
        reserved=((A, Decimal("20")), (B, Decimal(0))),
        funds=(),
        mode=FundAllocationMode.MANUAL,
        occurrences=events,
        overdue_count=0,
    )


def request(source: ProjectionSnapshot, **overrides: object) -> ScenarioRequest:
    return ScenarioRequest.model_validate(
        {
            "action": "expense",
            "amount": "90.0002",
            "account_id": str(A),
            "due_on": str(TODAY + timedelta(days=1)),
            "snapshot_id": fingerprint(source),
            **overrides,
        }
    )


def test_purchase_exact_delta_and_no_mutation() -> None:
    source = snapshot((event(10, "50", 4, OperationType.INCOME),))
    original = deepcopy(source)
    result = compare(source, request(source, stop_loss="10"))
    assert result.ending_free_delta == "-90.0002"
    assert Decimal(result.alternative.free.minimum_balance) == Decimal("-10.0001")
    assert result.alternative.zero_risk.windows[0].recovered_on == TODAY + timedelta(days=4)
    assert result.alternative.stop_loss_risk is not None
    assert source == original
    assert result == compare(source, request(source, stop_loss="10"))
    assert result.alternative.free.points[1].events[0].origin == "scenario"


def test_income_increases_end_and_no_evidence_omits_suggestion() -> None:
    source = snapshot()
    result = compare(source, request(source, action="income", amount="0.0001"))
    assert result.ending_free_delta == "0.0001"
    assert result.minimum_free_delta == "0.0000"  # actual starting point remains the minimum
    assert result.suggested_boundary is None


def test_amount_replaces_only_one_occurrence_and_noop_matches_baseline() -> None:
    source = snapshot((event(10, "50"), event(11, "10", 2)))
    base = dict(
        action="amount", account_id=None, due_on=None, occurrence_id=str(UUID(int=10)), version=1
    )
    result = compare(source, request(source, **base, amount="50"))
    assert Decimal(result.ending_free_delta) == 0
    assert result.baseline.free.ending_balance == result.alternative.free.ending_balance
    changed = compare(source, request(source, **base, amount="55.0001"))
    assert Decimal(changed.ending_free_delta) == Decimal("-5.0001")
    assert len(changed.alternative.free.points[1].events) == 1
    assert changed.alternative.free.points[2].events[0].origin == "plan"


def test_move_across_horizon_both_directions_and_daily_year_risk() -> None:
    source = snapshot((event(10, "100", 2), event(11, "100", 3, OperationType.INCOME)))
    values = dict(
        action="move", amount=None, account_id=None, occurrence_id=str(UUID(int=10)), version=1
    )
    later = compare(source, request(source, **values, due_on="2026-03-02"))
    assert Decimal(later.ending_free_delta) == 100
    assert "change_outside_horizon" in later.assumptions
    year = compare(source, request(source, **values, horizon="year", due_on="2026-02-04"))
    assert year.baseline.free.granularity == "month"
    assert year.baseline.zero_risk.windows[0].from_on == date(2026, 2, 2)
    assert year.baseline.zero_risk.windows[0].recovered_on == date(2026, 2, 3)
    assert year.alternative.zero_risk.windows == []
    outside = snapshot((event(10, "100", 35),))
    moved_in = compare(outside, request(outside, **values, due_on="2026-02-01"))
    assert Decimal(moved_in.ending_free_delta) == -100


def test_stop_loss_strict_comparison_and_unrecovered_window() -> None:
    source = replace(snapshot(), balances=((A, Decimal(100)), (B, Decimal(0))), reserved=())
    result = compare(source, request(source, amount="10", stop_loss="90"))
    assert result.alternative.stop_loss_risk is not None
    assert result.alternative.stop_loss_risk.windows == []
    risk = assess_risk(result.alternative.free, Decimal("90.0001"))
    assert risk.windows[0].recovered_on is None
    assert risk.windows[0].through_on == date(2026, 2, 28)


def test_initial_shortfall_recovering_today_is_preserved() -> None:
    source = replace(snapshot(), balances=((A, Decimal(0)), (B, Decimal(0))))
    result = compare(source, request(source, action="income", amount="30", due_on=str(TODAY)))
    window = result.alternative.zero_risk.windows[0]
    assert window.starts_at_snapshot
    assert window.recovered_on == TODAY
    assert window.minimum_balance == "-20"


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": 1.25},
        {"amount": "NaN"},
        {"amount": "1.00001"},
        {"amount": "-1"},
        {"amount": "0"},
        {"amount": "10000000000000000"},
        {"stop_loss": "-1"},
        {"due_on": None},
        {"account_id": None},
        {"fund_id": str(A)},
        {"action": "move"},
        {"action": "amount"},
        {"version": 2},
    ],
)
def test_invalid_request_shapes_and_money(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        request(snapshot(), **overrides)


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"due_on": "2026-01-30"}, "scenario_date"),
        ({"due_on": "2027-02-01"}, "scenario_date"),
        ({"scope_account_id": str(B)}, "scenario_scope"),
        ({"account_id": str(UUID(int=999))}, "scenario_account"),
        ({"snapshot_id": "0" * 64}, "scenario_stale"),
    ],
)
def test_invalid_references_and_dates(overrides: dict[str, object], code: str) -> None:
    with pytest.raises(ScenarioError, match=code):
        compare(snapshot(), request(snapshot(), **overrides))


def test_archived_account_cannot_receive_new_hypothesis() -> None:
    source = replace(snapshot(), accounts=(AccountIdentity(A, "Main", True),))
    with pytest.raises(ScenarioError, match="scenario_account"):
        compare(source, request(source))


def test_stale_occurrence_version_is_not_silently_applied() -> None:
    source = snapshot((event(10, "50"),))
    with pytest.raises(ScenarioError, match="scenario_source"):
        compare(
            source,
            request(
                source,
                action="amount",
                account_id=None,
                due_on=None,
                occurrence_id=str(UUID(int=10)),
                version=2,
            ),
        )


def fund(identity: int, balance: str, target: str) -> FundResponse:
    return FundResponse(
        id=UUID(int=identity),
        name=str(identity),
        description=None,
        allocation_percentage="50",
        manual_allocation_percentage="50",
        allocation_mode=FundAllocationMode.DYNAMIC,
        target_amount=target,
        total_balance=balance,
        remaining_amount=target,
        distribution_status="active",
        progress_percentage="0",
        archived=False,
        version=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_transfer_amount_recalculates_later_dynamic_funds_from_same_snapshot() -> None:
    source = replace(
        snapshot(
            (
                event(10, "50", 1, OperationType.TRANSFER, True),
                event(11, "80", 2, OperationType.TRANSFER, True),
            )
        ),
        funds=(fund(30, "0", "100"), fund(31, "50", "200")),
        mode=FundAllocationMode.DYNAMIC,
    )
    original = deepcopy(source)
    result = compare(
        source,
        request(
            source,
            action="amount",
            amount="120",
            account_id=None,
            due_on=None,
            occurrence_id=str(UUID(int=10)),
            version=1,
        ),
    )
    assert Decimal(result.ending_total_delta) == 0
    assert sum((Decimal(f.delta) for f in result.funds), Decimal(0)) == -Decimal(
        result.ending_free_delta
    )
    assert any(Decimal(f.delta) != 0 for f in result.funds)
    assert source == original
    single = compare(
        source,
        request(
            source,
            action="amount",
            amount="120",
            account_id=None,
            due_on=None,
            occurrence_id=str(UUID(int=10)),
            version=1,
            scope_account_id=str(B),
        ),
    )
    assert single.funds == result.funds
    assert Decimal(single.ending_total_delta) == 70


def test_pure_projection_empty_overlay_and_order_independence() -> None:
    source = snapshot((event(10, "10"), event(11, "40", 2, OperationType.INCOME)))
    baseline = project_snapshot(
        source, through_on=date(2026, 2, 28), horizon=ForecastHorizon.MONTH, account_id=None
    )
    assert baseline == project_snapshot(
        source,
        occurrences=source.occurrences,
        through_on=date(2026, 2, 28),
        horizon=ForecastHorizon.MONTH,
        account_id=None,
    )
    assert baseline == project_snapshot(
        source,
        occurrences=tuple(reversed(source.occurrences)),
        through_on=date(2026, 2, 28),
        horizon=ForecastHorizon.MONTH,
        account_id=None,
    )


def test_dynamic_overflow_is_reserved_not_free_money() -> None:
    source = replace(
        snapshot((event(10, "50", 1, OperationType.TRANSFER, True),)),
        funds=(fund(30, "0", "10"),),
        mode=FundAllocationMode.DYNAMIC,
    )
    result = compare(
        source,
        request(
            source,
            action="amount",
            amount="70",
            account_id=None,
            due_on=None,
            occurrence_id=str(UUID(int=10)),
            version=1,
        ),
    )
    assert Decimal(result.ending_total_delta) == 0
    assert Decimal(result.ending_free_delta) == -20
    assert Decimal(result.reserve.baseline) == 40
    assert Decimal(result.reserve.alternative) == 60
    assert Decimal(result.funds[0].delta) == 0
    assert Decimal(result.events[0].alternative_reserve) == 60


def test_downstream_fund_changes_are_explained_even_when_total_allocation_is_unchanged() -> None:
    source = replace(
        snapshot(
            (
                event(10, "50", 1, OperationType.TRANSFER, True),
                event(11, "80", 2, OperationType.TRANSFER, True),
            )
        ),
        funds=(fund(30, "0", "100"), fund(31, "50", "200")),
        mode=FundAllocationMode.DYNAMIC,
    )
    result = compare(
        source,
        request(
            source,
            action="amount",
            amount="100",
            account_id=None,
            due_on=None,
            occurrence_id=str(UUID(int=10)),
            version=1,
        ),
    )
    downstream = next(item for item in result.events if item.occurrence_id == UUID(int=11))
    assert downstream.baseline_allocation == downstream.alternative_allocation
    assert any(part.baseline != part.alternative for part in downstream.allocations)
    assert not downstream.hypothetical


def test_projection_excludes_nonactionable_fund_transfers_defensively() -> None:
    source = replace(
        snapshot(
            (
                replace(
                    event(10, "50", 1, OperationType.TRANSFER, True),
                    status=OccurrenceStatus.CONFIRMED,
                ),
            )
        ),
        funds=(fund(30, "0", "10"),),
        mode=FundAllocationMode.DYNAMIC,
    )
    result = project_snapshot(
        source, through_on=date(2026, 2, 28), horizon=ForecastHorizon.MONTH, account_id=None
    )
    assert result.funds.events == []
    assert result.free.starting_balance == result.free.ending_balance
