from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.modules.accounts.contracts import AccountIdentity, AccountReferenceError
from app.modules.forecasting.schemas import ForecastBalanceMode, ForecastHorizon, ForecastResponse
from app.modules.forecasting.service import (
    ForecastInputEvent,
    build_forecast,
    build_fund_forecast,
    calculate_forecast,
    horizon_end,
    project_fund_allocations,
)
from app.modules.funds.schemas import FundResponse
from app.modules.operations.contracts import OperationType
from app.modules.scheduling.contracts import (
    ForecastScheduleSnapshot,
    OccurrenceStatus,
    PlannedOccurrence,
)
from app.modules.settings.contracts import FundAllocationMode

TODAY = date(2026, 8, 12)
SOURCE = UUID("10000000-0000-0000-0000-000000000001")
TARGET = UUID("10000000-0000-0000-0000-000000000002")
RULE = UUID("20000000-0000-0000-0000-000000000001")


def event(
    suffix: int,
    *,
    due_on: date,
    type: OperationType,
    amount: str,
    account_id: UUID = SOURCE,
    destination_account_id: UUID | None = None,
    status: OccurrenceStatus = OccurrenceStatus.PENDING,
    reserved_amount: str = "0",
) -> ForecastInputEvent:
    return ForecastInputEvent(
        occurrence_id=UUID(f"30000000-0000-0000-0000-{suffix:012d}"),
        rule_id=RULE,
        due_on=due_on,
        type=type,
        status=status,
        description=f"event {suffix}",
        account_id=account_id,
        destination_account_id=destination_account_id,
        amount=Decimal(amount),
        reserved_amount=Decimal(reserved_amount),
    )


def test_horizons_are_calendar_bounded() -> None:
    assert horizon_end(TODAY, ForecastHorizon.TWO_WEEKS) == date(2026, 8, 26)
    assert horizon_end(date(2026, 1, 31), ForecastHorizon.MONTH) == date(2026, 2, 28)
    assert horizon_end(TODAY, ForecastHorizon.QUARTER) == date(2026, 11, 12)
    assert horizon_end(TODAY, ForecastHorizon.HALF_YEAR) == date(2027, 2, 12)
    assert horizon_end(TODAY, ForecastHorizon.YEAR) == date(2027, 8, 12)


def test_two_week_forecast_includes_its_inclusive_end() -> None:
    through_on = horizon_end(TODAY, ForecastHorizon.TWO_WEEKS)
    result = calculate_forecast(
        today=TODAY,
        through_on=through_on,
        balances={SOURCE: Decimal("100.0000")},
        account_name_by_id={SOURCE: "Main"},
        events=[
            event(1, due_on=through_on, type=OperationType.EXPENSE, amount="10.0000"),
        ],
        account_id=SOURCE,
        horizon=ForecastHorizon.TWO_WEEKS,
    )

    assert len(result.points) == 15
    assert result.points[-1].on == through_on
    assert result.ending_balance == "90.0000"


def test_fund_forecast_applies_only_flagged_transfers_with_exact_rounding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fund_id = UUID("40000000-0000-0000-0000-000000000001")
    occurrence = PlannedOccurrence(
        id=UUID("30000000-0000-0000-0000-000000000001"),
        rule_id=RULE,
        due_on=date(2026, 8, 13),
        type=OperationType.TRANSFER,
        amount=Decimal("10.0001"),
        description=None,
        account_id=SOURCE,
        destination_account_id=TARGET,
        allocate_to_funds=True,
        status=OccurrenceStatus.PENDING,
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.forecast_schedule_snapshot",
        lambda *args, **kwargs: ForecastScheduleSnapshot(occurrences=[occurrence], overdue_count=0),
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.list_account_identities",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.locked_active_funds",
        lambda *args, **kwargs: [
            FundResponse(
                id=fund_id,
                name="Резерв",
                description=None,
                allocation_percentage="33.3300",
                manual_allocation_percentage="33.3300",
                allocation_mode=FundAllocationMode.MANUAL,
                target_amount=None,
                total_balance="5.0000",
                remaining_amount=None,
                distribution_status="manual",
                progress_percentage=None,
                archived=False,
                version=1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ],
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.fund_allocation_mode",
        lambda *args, **kwargs: FundAllocationMode.MANUAL,
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.reserve_balances",
        lambda *args, **kwargs: {},
    )

    result = build_fund_forecast(
        cast(Session, object()),
        today=TODAY,
        horizon=ForecastHorizon.TWO_WEEKS,
    )

    assert result.planned_transfer_total == "10.0001"
    assert result.planned_allocation_total == "3.3330"
    assert result.unallocated_total == "6.6671"
    assert result.series[0].starting_balance == "5.0000"
    assert result.series[0].ending_balance == "8.3330"
    assert result.series[0].points[1].change == "3.3330"


def test_dynamic_fund_forecast_recalculates_before_each_planned_replenishment() -> None:
    first_id = UUID("40000000-0000-0000-0000-000000000001")
    second_id = UUID("40000000-0000-0000-0000-000000000002")
    now = datetime.now(UTC)
    funds = [
        FundResponse(
            id=first_id,
            name="Первый",
            description=None,
            allocation_percentage="65.0000",
            manual_allocation_percentage="0",
            allocation_mode=FundAllocationMode.DYNAMIC,
            target_amount="100.0000",
            total_balance="0",
            remaining_amount="100.0000",
            distribution_status="active",
            progress_percentage="0.00",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        ),
        FundResponse(
            id=second_id,
            name="Второй",
            description=None,
            allocation_percentage="35.0000",
            manual_allocation_percentage="0",
            allocation_mode=FundAllocationMode.DYNAMIC,
            target_amount="100.0000",
            total_balance="50.0000",
            remaining_amount="50.0000",
            distribution_status="active",
            progress_percentage="50.00",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        ),
    ]
    occurrences = [
        PlannedOccurrence(
            id=UUID(f"50000000-0000-0000-0000-{index:012d}"),
            rule_id=RULE,
            due_on=date(2026, 8, 12 + index),
            type=OperationType.TRANSFER,
            amount=Decimal("100"),
            description=None,
            account_id=SOURCE,
            destination_account_id=TARGET,
            allocate_to_funds=True,
            status=OccurrenceStatus.PENDING,
        )
        for index in (1, 2)
    ]

    projection = project_fund_allocations(funds, occurrences, FundAllocationMode.DYNAMIC)

    assert projection.events[0].percentages == {
        first_id: Decimal("65.0000"),
        second_id: Decimal("35.0000"),
    }
    assert projection.events[1].percentages == {
        first_id: Decimal("68.0000"),
        second_id: Decimal("32.0000"),
    }
    assert projection.ending_balances == {
        first_id: Decimal("100.0000"),
        second_id: Decimal("100.0000"),
    }
    assert projection.events[1].reserve_amount == Decimal("50.0000")
    assert projection.ending_percentages == {}


def test_dynamic_fund_forecast_uses_relative_progress_for_different_targets() -> None:
    first_id = UUID("41000000-0000-0000-0000-000000000001")
    second_id = UUID("41000000-0000-0000-0000-000000000002")
    now = datetime.now(UTC)
    funds = [
        FundResponse(
            id=first_id,
            name="Небольшая цель",
            description=None,
            allocation_percentage="50.0000",
            manual_allocation_percentage="0",
            allocation_mode=FundAllocationMode.DYNAMIC,
            target_amount="100.0000",
            total_balance="50.0000",
            remaining_amount="50.0000",
            distribution_status="active",
            progress_percentage="50.00",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        ),
        FundResponse(
            id=second_id,
            name="Большая цель",
            description=None,
            allocation_percentage="50.0000",
            manual_allocation_percentage="0",
            allocation_mode=FundAllocationMode.DYNAMIC,
            target_amount="1000.0000",
            total_balance="500.0000",
            remaining_amount="500.0000",
            distribution_status="active",
            progress_percentage="50.00",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        ),
    ]
    occurrences = [
        PlannedOccurrence(
            id=UUID(f"51000000-0000-0000-0000-{index:012d}"),
            rule_id=RULE,
            due_on=date(2026, 8, 12 + index),
            type=OperationType.TRANSFER,
            amount=Decimal("100"),
            description=None,
            account_id=SOURCE,
            destination_account_id=TARGET,
            allocate_to_funds=True,
            status=OccurrenceStatus.PENDING,
        )
        for index in (1, 2)
    ]

    projection = project_fund_allocations(funds, occurrences, FundAllocationMode.DYNAMIC)

    assert projection.events[0].percentages == {
        first_id: Decimal("50.0000"),
        second_id: Decimal("50.0000"),
    }
    assert projection.events[1].percentages == {second_id: Decimal("100.0000")}
    assert projection.ending_balances == {
        first_id: Decimal("100.0000"),
        second_id: Decimal("650.0000"),
    }
    assert projection.ending_percentages == {second_id: Decimal("100.0000")}


def test_selected_free_forecast_uses_one_global_schedule_lock_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = PlannedOccurrence(
        id=UUID("30000000-0000-0000-0000-000000000001"),
        rule_id=RULE,
        due_on=date(2026, 8, 13),
        type=OperationType.EXPENSE,
        amount=Decimal("10"),
        description=None,
        account_id=SOURCE,
        destination_account_id=None,
        allocate_to_funds=False,
        status=OccurrenceStatus.PENDING,
    )
    unrelated = PlannedOccurrence(
        id=UUID("30000000-0000-0000-0000-000000000002"),
        rule_id=RULE,
        due_on=date(2026, 8, 13),
        type=OperationType.EXPENSE,
        amount=Decimal("50"),
        description=None,
        account_id=TARGET,
        destination_account_id=None,
        allocate_to_funds=False,
        status=OccurrenceStatus.PENDING,
    )
    calls: list[UUID | None] = []

    def schedule_snapshot(*args: object, **kwargs: object) -> ForecastScheduleSnapshot:
        calls.append(cast(UUID | None, kwargs["account_id"]))
        return ForecastScheduleSnapshot(
            occurrences=[selected, unrelated],
            overdue_count=3,
            overdue_count_by_account={SOURCE: 2, TARGET: 1},
        )

    monkeypatch.setattr(
        "app.modules.forecasting.service.forecast_schedule_snapshot", schedule_snapshot
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.list_account_identities",
        lambda *args, **kwargs: [
            AccountIdentity(SOURCE, "Main", False),
            AccountIdentity(TARGET, "Other", False),
        ],
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.account_names",
        lambda *args, **kwargs: {SOURCE: "Main", TARGET: "Other"},
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.account_balances",
        lambda *args, **kwargs: {SOURCE: Decimal("100"), TARGET: Decimal("100")},
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.reserved_balances",
        lambda *args, **kwargs: {SOURCE: Decimal(0), TARGET: Decimal(0)},
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.locked_active_funds", lambda *args, **kwargs: []
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.fund_allocation_mode",
        lambda *args, **kwargs: FundAllocationMode.DYNAMIC,
    )

    result = build_forecast(
        cast(Session, object()),
        today=TODAY,
        horizon=ForecastHorizon.TWO_WEEKS,
        account_id=SOURCE,
    )

    assert calls == [None]
    assert result.overdue_excluded_count == 2
    assert result.ending_balance == "90"
    assert sum(len(point.events) for point in result.points) == 1


def test_account_forecast_is_exact_deterministic_and_explained() -> None:
    events = [
        event(2, due_on=date(2026, 8, 13), type=OperationType.EXPENSE, amount="40.0000"),
        event(1, due_on=date(2026, 8, 13), type=OperationType.INCOME, amount="10.0000"),
        event(3, due_on=date(2026, 8, 14), type=OperationType.EXPENSE, amount="80.0000"),
    ]

    def calculate(items: list[ForecastInputEvent]) -> ForecastResponse:
        return calculate_forecast(
            today=TODAY,
            through_on=date(2026, 8, 19),
            balances={SOURCE: Decimal("100.0000")},
            account_name_by_id={SOURCE: "Main"},
            events=items,
            account_id=SOURCE,
            horizon=ForecastHorizon.TWO_WEEKS,
        )

    first = calculate(events)
    second = calculate(list(reversed(events)))

    assert first == second
    assert first.starting_balance == "100.0000"
    assert first.ending_balance == "-10.0000"
    assert first.minimum_balance == "-10.0000"
    assert first.minimum_on == date(2026, 8, 14)
    assert first.first_negative_on == date(2026, 8, 14)
    assert first.first_negative_balance == "-10.0000"
    assert first.expected_income == "10.0000"
    assert first.expected_expense == "120.0000"
    assert first.granularity == "day"
    assert len(first.points) == 8
    assert [point.on for point in first.points[:3]] == [
        date(2026, 8, 12),
        date(2026, 8, 13),
        date(2026, 8, 14),
    ]
    assert first.points[1].opening_balance == "100.0000"
    assert first.points[1].change == "-30.0000"
    assert [item.effect for item in first.points[1].events] == ["10.0000", "-40.0000"]


def test_transfer_is_neutral_for_all_accounts_and_directional_for_one() -> None:
    transfer = event(
        1,
        due_on=date(2026, 8, 13),
        type=OperationType.TRANSFER,
        amount="25.0000",
        destination_account_id=TARGET,
    )

    def calculate(account_id: UUID | None) -> ForecastResponse:
        return calculate_forecast(
            today=TODAY,
            through_on=date(2026, 8, 19),
            balances={SOURCE: Decimal("100.0000"), TARGET: Decimal("20.0000")},
            account_name_by_id={SOURCE: "Main", TARGET: "Savings"},
            events=[transfer],
            account_id=account_id,
            horizon=ForecastHorizon.TWO_WEEKS,
        )

    combined = calculate(None)
    source = calculate(SOURCE)
    target = calculate(TARGET)

    assert combined.starting_balance == combined.ending_balance == "120.0000"
    assert combined.points[1].events[0].effect == "0"
    assert combined.expected_income == combined.expected_expense == "0"
    assert combined.first_negative_on is None
    assert combined.first_negative_balance is None
    assert source.ending_balance == "75.0000"
    assert target.ending_balance == "45.0000"


def test_allocating_transfer_reduces_only_free_money_forecast() -> None:
    transfer = event(
        1,
        due_on=date(2026, 8, 13),
        type=OperationType.TRANSFER,
        amount="100.0000",
        destination_account_id=TARGET,
        reserved_amount="60.0000",
    )

    def calculate(account_id: UUID | None, mode: ForecastBalanceMode) -> ForecastResponse:
        return calculate_forecast(
            today=TODAY,
            through_on=date(2026, 8, 19),
            balances={SOURCE: Decimal("100.0000"), TARGET: Decimal("20.0000")},
            account_name_by_id={SOURCE: "Main", TARGET: "Savings"},
            events=[transfer],
            account_id=account_id,
            horizon=ForecastHorizon.TWO_WEEKS,
            balance_mode=mode,
        )

    free = calculate(None, ForecastBalanceMode.FREE)
    total = calculate(None, ForecastBalanceMode.TOTAL)
    free_target = calculate(TARGET, ForecastBalanceMode.FREE)

    assert free.ending_balance == "60.0000"
    assert free.points[1].events[0].effect == "-60.0000"
    assert total.ending_balance == "120.0000"
    assert total.points[1].events[0].effect == "0"
    assert free_target.ending_balance == "60.0000"


def test_account_forecast_omits_events_for_other_accounts() -> None:
    other_account_event = event(
        3,
        due_on=date(2026, 8, 13),
        type=OperationType.EXPENSE,
        amount="10.0000",
        account_id=TARGET,
    )

    result = calculate_forecast(
        today=TODAY,
        through_on=date(2026, 8, 19),
        balances={SOURCE: Decimal("100.0000"), TARGET: Decimal("50.0000")},
        account_name_by_id={SOURCE: "Main", TARGET: "Other"},
        events=[other_account_event],
        account_id=SOURCE,
        horizon=ForecastHorizon.TWO_WEEKS,
    )

    assert result.ending_balance == "100.0000"
    assert all(not point.events for point in result.points)


def test_non_actionable_events_are_defensively_excluded() -> None:
    result = calculate_forecast(
        today=TODAY,
        through_on=date(2026, 8, 19),
        balances={SOURCE: Decimal("100.0000")},
        account_name_by_id={SOURCE: "Main"},
        events=[
            event(
                4,
                due_on=date(2026, 8, 13),
                type=OperationType.INCOME,
                amount="50.0000",
                status=OccurrenceStatus.CONFIRMED,
            ),
            event(
                5,
                due_on=date(2026, 8, 14),
                type=OperationType.EXPENSE,
                amount="25.0000",
                status=OccurrenceStatus.CANCELLED,
            ),
        ],
        account_id=SOURCE,
        horizon=ForecastHorizon.TWO_WEEKS,
    )

    assert result.starting_balance == result.ending_balance == "100.0000"
    assert all(not point.events for point in result.points)


def test_invalid_account_scope_is_rejected() -> None:
    with pytest.raises(AccountReferenceError):
        calculate_forecast(
            today=TODAY,
            through_on=date(2026, 8, 19),
            balances={SOURCE: Decimal("0")},
            account_name_by_id={SOURCE: "Main"},
            events=[],
            account_id=TARGET,
            horizon=ForecastHorizon.TWO_WEEKS,
        )


def test_year_forecast_uses_monthly_periods_and_keeps_event_details() -> None:
    result = calculate_forecast(
        today=TODAY,
        through_on=date(2027, 8, 12),
        balances={SOURCE: Decimal("100.0000")},
        account_name_by_id={SOURCE: "Main"},
        events=[
            event(1, due_on=date(2026, 8, 13), type=OperationType.INCOME, amount="20.0000"),
            event(2, due_on=date(2026, 8, 20), type=OperationType.EXPENSE, amount="5.0000"),
            event(3, due_on=date(2026, 9, 1), type=OperationType.EXPENSE, amount="10.0000"),
        ],
        account_id=SOURCE,
        horizon=ForecastHorizon.YEAR,
    )

    assert result.granularity == "month"
    assert len(result.points) == 13
    assert result.points[0].period_from == TODAY
    assert result.points[0].on == date(2026, 8, 31)
    assert result.points[0].change == "15.0000"
    assert len(result.points[0].events) == 2
    assert result.points[1].period_from == date(2026, 9, 1)
    assert result.points[1].on == date(2026, 9, 30)
    assert result.points[-1].on == date(2027, 8, 12)


def test_first_negative_balance_keeps_daily_precision_for_year_view() -> None:
    result = calculate_forecast(
        today=TODAY,
        through_on=date(2027, 8, 12),
        balances={SOURCE: Decimal("20.0000")},
        account_name_by_id={SOURCE: "Main"},
        events=[
            event(1, due_on=date(2026, 8, 13), type=OperationType.EXPENSE, amount="22.0000"),
            event(2, due_on=date(2026, 8, 20), type=OperationType.INCOME, amount="10.0000"),
        ],
        account_id=SOURCE,
        horizon=ForecastHorizon.YEAR,
    )

    assert result.first_negative_on == date(2026, 8, 13)
    assert result.first_negative_balance == "-2.0000"
    assert result.points[0].closing_balance == "8.0000"


def test_starting_deficit_keeps_the_current_balance_as_first_negative() -> None:
    result = calculate_forecast(
        today=TODAY,
        through_on=date(2026, 8, 19),
        balances={SOURCE: Decimal("-7.5000")},
        account_name_by_id={SOURCE: "Main"},
        events=[
            event(1, due_on=TODAY, type=OperationType.INCOME, amount="20.0000"),
        ],
        account_id=SOURCE,
        horizon=ForecastHorizon.TWO_WEEKS,
    )

    assert result.first_negative_on == TODAY
    assert result.first_negative_balance == "-7.5000"
    assert result.points[0].closing_balance == "12.5000"


@pytest.mark.parametrize("account_id", [None, SOURCE, TARGET])
@pytest.mark.parametrize("mode", list(ForecastBalanceMode))
@pytest.mark.parametrize("capacity", [None, "0", "20", "40.0001"])
def test_dynamic_reservation_is_included_in_free_projection(
    monkeypatch: pytest.MonkeyPatch,
    account_id: UUID | None,
    mode: ForecastBalanceMode,
    capacity: str | None,
) -> None:
    """Cover partial/full capacity and no funds through the composed read model."""
    now = datetime.now(UTC)
    funds = (
        []
        if capacity is None
        else [
            FundResponse(
                id=RULE,
                name="Goal",
                description=None,
                allocation_percentage="100",
                manual_allocation_percentage="0",
                allocation_mode=FundAllocationMode.DYNAMIC,
                target_amount=str(Decimal("100") + Decimal(capacity)),
                total_balance="100",
                remaining_amount=capacity,
                distribution_status="active",
                progress_percentage=None,
                archived=False,
                version=1,
                created_at=now,
                updated_at=now,
            )
        ]
    )
    occurrences = [
        PlannedOccurrence(
            id=UUID(f"30000000-0000-0000-0000-{index:012d}"),
            rule_id=RULE,
            due_on=TODAY,
            type=OperationType.TRANSFER,
            amount=Decimal(amount),
            description=None,
            account_id=SOURCE,
            destination_account_id=TARGET,
            allocate_to_funds=True,
            status=OccurrenceStatus.PENDING,
        )
        for index, amount in [(1, "30.0001"), (2, "10")]
    ]
    monkeypatch.setattr(
        "app.modules.forecasting.service.forecast_schedule_snapshot",
        lambda *a, **k: ForecastScheduleSnapshot(occurrences, 0),
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.list_account_identities",
        lambda *a, **k: [
            AccountIdentity(SOURCE, "Main", False),
            AccountIdentity(TARGET, "Savings", False),
        ],
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.account_names",
        lambda *a, **k: {SOURCE: "Main", TARGET: "Savings"},
    )
    monkeypatch.setattr(
        "app.modules.forecasting.service.account_balances",
        lambda *a, **k: {SOURCE: Decimal("200"), TARGET: Decimal("120")},
    )
    # Existing reservations include both fund positions and a 20-unit reserve.
    reserved = Decimal("20") + (Decimal("100") if funds else Decimal(0))
    monkeypatch.setattr(
        "app.modules.forecasting.service.reserved_balances",
        lambda *a, **k: {SOURCE: Decimal(0), TARGET: reserved},
    )
    monkeypatch.setattr("app.modules.forecasting.service.locked_active_funds", lambda *a: funds)
    monkeypatch.setattr(
        "app.modules.forecasting.service.fund_allocation_mode",
        lambda *a: FundAllocationMode.DYNAMIC,
    )
    result = build_forecast(
        cast(Session, object()),
        today=TODAY,
        horizon=ForecastHorizon.MONTH,
        account_id=account_id,
        balance_mode=mode,
    )
    starting = {None: Decimal("320"), SOURCE: Decimal("200"), TARGET: Decimal("120")}[account_id]
    if mode == ForecastBalanceMode.FREE and account_id != SOURCE:
        starting -= reserved
    change = Decimal("-40.0001") if account_id == SOURCE else Decimal(0)
    if account_id == TARGET and mode == ForecastBalanceMode.TOTAL:
        change = Decimal("40.0001")
    if account_id is None and mode == ForecastBalanceMode.FREE:
        change = Decimal("-40.0001")
    assert Decimal(result.starting_balance) == starting
    assert Decimal(result.ending_balance) == starting + change
    assert Decimal(result.expected_expense) == 0
    assert sum((Decimal(e.effect) for p in result.points for e in p.events), Decimal(0)) == change
