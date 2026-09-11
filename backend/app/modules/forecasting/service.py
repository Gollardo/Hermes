from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.accounts.contracts import (
    AccountReferenceError,
    account_names,
    list_account_identities,
)
from app.modules.forecasting.schemas import (
    ForecastBalanceMode,
    ForecastEventResponse,
    ForecastGranularity,
    ForecastHorizon,
    ForecastPointResponse,
    ForecastResponse,
    ForecastScope,
    FundForecastAllocationEventResponse,
    FundForecastAllocationItemResponse,
    FundForecastPointResponse,
    FundForecastResponse,
    FundForecastSeriesResponse,
)
from app.modules.funds.contracts import (
    FundDistributionState,
    FundResponse,
    dynamic_capacity_allocations,
    dynamic_percentages,
    locked_active_funds,
    percentage_allocations,
    reserve_balances,
    reserved_balances,
)
from app.modules.operations.contracts import OperationType, account_balances
from app.modules.scheduling.contracts import (
    ForecastScheduleSnapshot,
    OccurrenceSourceKind,
    OccurrenceStatus,
    PlannedOccurrence,
    forecast_schedule_snapshot,
)
from app.modules.settings.contracts import FundAllocationMode, fund_allocation_mode


@dataclass(frozen=True, slots=True)
class ForecastInputEvent:
    occurrence_id: UUID
    rule_id: UUID | None
    due_on: date
    type: OperationType
    status: OccurrenceStatus
    description: str | None
    account_id: UUID
    destination_account_id: UUID | None
    amount: Decimal
    allocated_to_funds: Decimal = Decimal(0)
    source_kind: OccurrenceSourceKind = OccurrenceSourceKind.RECURRING
    origin: Literal["plan", "scenario"] = "plan"


@dataclass(frozen=True, slots=True)
class ProjectedAllocation:
    occurrence_id: UUID
    due_on: date
    incoming_amount: Decimal
    percentages: dict[UUID, Decimal]
    amounts: dict[UUID, Decimal]
    reserve_amount: Decimal = Decimal(0)


@dataclass(frozen=True, slots=True)
class FundAllocationProjection:
    mode: FundAllocationMode
    starting_balances: dict[UUID, Decimal]
    ending_balances: dict[UUID, Decimal]
    starting_percentages: dict[UUID, Decimal]
    ending_percentages: dict[UUID, Decimal]
    events: list[ProjectedAllocation]


def project_fund_allocations(
    funds: list[FundResponse],
    occurrences: list[PlannedOccurrence],
    mode: FundAllocationMode,
) -> FundAllocationProjection:
    """Apply planned allocations sequentially without mutating actual fund state."""
    balances = {fund.id: Decimal(fund.total_balance) for fund in funds}
    starting_balances = dict(balances)
    targets = {
        fund.id: Decimal(fund.target_amount) if fund.target_amount is not None else None
        for fund in funds
    }
    manual_percentages = [
        (fund.id, Decimal(fund.manual_allocation_percentage))
        for fund in funds
        if Decimal(fund.manual_allocation_percentage) > 0
    ]

    def percentages() -> list[tuple[UUID, Decimal]]:
        if mode == FundAllocationMode.MANUAL:
            return manual_percentages
        return dynamic_percentages(
            [
                FundDistributionState(
                    fund_id=fund.id,
                    balance=balances[fund.id],
                    target_amount=targets[fund.id],
                )
                for fund in funds
            ]
        )

    starting_percentages = dict(percentages())
    events: list[ProjectedAllocation] = []
    for occurrence in sorted(occurrences, key=lambda item: (item.due_on, item.id)):
        if not occurrence.allocate_to_funds:
            continue
        current_percentages = percentages()
        if mode == FundAllocationMode.DYNAMIC:
            allocations, reserve_amount = dynamic_capacity_allocations(
                occurrence.amount,
                [
                    FundDistributionState(fund.id, balances[fund.id], targets[fund.id])
                    for fund in funds
                ],
            )
        else:
            allocations = percentage_allocations(occurrence.amount, current_percentages)
            reserve_amount = Decimal(0)
        amounts = {item.fund_id: item.amount for item in allocations if item.amount > 0}
        for fund_id, amount in amounts.items():
            balances[fund_id] += amount
        events.append(
            ProjectedAllocation(
                occurrence_id=occurrence.id,
                due_on=occurrence.due_on,
                incoming_amount=occurrence.amount,
                percentages=dict(current_percentages),
                amounts=amounts,
                reserve_amount=reserve_amount,
            )
        )
    return FundAllocationProjection(
        mode=mode,
        starting_balances=starting_balances,
        ending_balances=balances,
        starting_percentages=starting_percentages,
        ending_percentages=dict(percentages()),
        events=events,
    )


def horizon_end(today: date, horizon: ForecastHorizon) -> date:
    if horizon == ForecastHorizon.TWO_WEEKS:
        return today + timedelta(days=14)
    if horizon == ForecastHorizon.MONTH:
        return _add_months(today, 1)
    if horizon == ForecastHorizon.QUARTER:
        return _add_months(today, 3)
    if horizon == ForecastHorizon.HALF_YEAR:
        return _add_months(today, 6)
    return _add_months(today, 12)


def _add_months(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(index, 12)
    month = month_index + 1
    next_index = index + 1
    next_year, next_month_index = divmod(next_index, 12)
    last_day = (date(next_year, next_month_index + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(value.day, last_day))


def calculate_forecast(
    *,
    today: date,
    through_on: date,
    balances: dict[UUID, Decimal],
    account_name_by_id: dict[UUID, str],
    events: list[ForecastInputEvent],
    account_id: UUID | None,
    horizon: ForecastHorizon,
    overdue_excluded_count: int = 0,
    balance_mode: ForecastBalanceMode = ForecastBalanceMode.TOTAL,
) -> ForecastResponse:
    if through_on < today:
        raise ValueError("forecast end must not precede today")
    if account_id is not None and account_id not in balances:
        raise AccountReferenceError
    starting = (
        balances[account_id] if account_id is not None else sum(balances.values(), Decimal(0))
    )
    grouped: dict[date, list[tuple[ForecastInputEvent, Decimal]]] = defaultdict(list)
    income = Decimal(0)
    expense = Decimal(0)
    for event in sorted(events, key=lambda item: (item.due_on, item.occurrence_id)):
        if event.status not in {OccurrenceStatus.PENDING, OccurrenceStatus.POSTPONED}:
            continue
        if event.due_on < today or event.due_on > through_on:
            continue
        if account_id is not None and account_id not in {
            event.account_id,
            event.destination_account_id,
        }:
            continue
        effect = _scope_effect(event, account_id, balance_mode)
        grouped[event.due_on].append((event, effect))
        if event.type == OperationType.INCOME and effect > 0:
            income += effect
        elif event.type == OperationType.EXPENSE and effect < 0:
            expense += -effect

    granularity = (
        ForecastGranularity.MONTH if horizon == ForecastHorizon.YEAR else ForecastGranularity.DAY
    )
    minimum = starting
    minimum_on = today
    first_negative: date | None = today if starting < 0 else None
    first_negative_balance: Decimal | None = starting if starting < 0 else None
    risk_balance = starting
    for on in sorted(grouped):
        risk_balance += sum((effect for _, effect in grouped[on]), Decimal(0))
        if risk_balance < minimum:
            minimum = risk_balance
            minimum_on = on
        if first_negative is None and risk_balance < 0:
            first_negative = on
            first_negative_balance = risk_balance

    current = starting
    points: list[ForecastPointResponse] = []
    for period_from, on in _forecast_periods(today, through_on, granularity):
        opening = current
        period_events = [
            item
            for event_on in sorted(grouped)
            if period_from <= event_on <= on
            for item in grouped[event_on]
        ]
        change = sum((effect for _, effect in period_events), Decimal(0))
        current += change
        points.append(
            ForecastPointResponse(
                period_from=period_from,
                on=on,
                opening_balance=_money(opening),
                change=_money(change),
                closing_balance=_money(current),
                events=[
                    _event_response(event, effect, account_name_by_id)
                    for event, effect in period_events
                ],
            )
        )
    return ForecastResponse(
        balance_mode=balance_mode,
        scope=ForecastScope.ACCOUNT if account_id is not None else ForecastScope.ALL,
        account_id=account_id,
        account_name=account_name_by_id.get(account_id) if account_id is not None else None,
        horizon=horizon,
        granularity=granularity,
        from_on=today,
        through_on=through_on,
        starting_balance=_money(starting),
        ending_balance=_money(current),
        minimum_balance=_money(minimum),
        minimum_on=minimum_on,
        first_negative_on=first_negative,
        first_negative_balance=(
            _money(first_negative_balance) if first_negative_balance is not None else None
        ),
        expected_income=_money(income),
        expected_expense=_money(expense),
        overdue_excluded_count=overdue_excluded_count,
        points=points,
    )


def _forecast_periods(
    from_on: date, through_on: date, granularity: ForecastGranularity
) -> list[tuple[date, date]]:
    if granularity == ForecastGranularity.DAY:
        return [
            (from_on + timedelta(days=offset), from_on + timedelta(days=offset))
            for offset in range((through_on - from_on).days + 1)
        ]
    periods: list[tuple[date, date]] = []
    cursor = from_on
    while cursor <= through_on:
        month_end = _add_months(cursor.replace(day=1), 1) - timedelta(days=1)
        period_end = min(month_end, through_on)
        periods.append((cursor, period_end))
        cursor = period_end + timedelta(days=1)
    return periods


def build_forecast(
    session: Session,
    *,
    today: date,
    horizon: ForecastHorizon,
    account_id: UUID | None,
    balance_mode: ForecastBalanceMode = ForecastBalanceMode.FREE,
) -> ForecastResponse:
    through_on = horizon_end(today, horizon)
    schedule_account_id = None if balance_mode == ForecastBalanceMode.FREE else account_id
    allocation_schedule = forecast_schedule_snapshot(
        session,
        today=today,
        due_to=through_on,
        account_id=schedule_account_id,
    )
    schedule = allocation_schedule
    if balance_mode == ForecastBalanceMode.FREE and account_id is not None:
        schedule = ForecastScheduleSnapshot(
            occurrences=[
                item
                for item in allocation_schedule.occurrences
                if account_id in {item.account_id, item.destination_account_id}
            ],
            overdue_count=allocation_schedule.overdue_count_by_account.get(account_id, 0),
        )
    # Preserve the Scheduling -> Accounts lock order used by confirmation and
    # rule replacement. Shared locks keep both the plan and actual ledger at one
    # coherent transaction point without introducing a reverse lock dependency.
    accounts = list_account_identities(session, shared_lock=True)
    account_ids = {account.id for account in accounts}
    if account_id is not None and account_id not in account_ids:
        raise AccountReferenceError
    names = account_names(session, account_ids)
    balances = account_balances(session, account_ids)
    allocated_by_occurrence: dict[UUID, Decimal] = {}
    if balance_mode == ForecastBalanceMode.FREE:
        reserved_by_account = reserved_balances(session, account_ids)
        balances = {
            identity: balance - reserved_by_account[identity]
            for identity, balance in balances.items()
        }
        funds = locked_active_funds(session)
        mode = fund_allocation_mode(session)
        projection = project_fund_allocations(
            funds,
            allocation_schedule.occurrences,
            mode,
        )
        allocated_by_occurrence = {
            event.occurrence_id: sum(event.amounts.values(), Decimal(0)) + event.reserve_amount
            for event in projection.events
        }
    return calculate_forecast(
        today=today,
        through_on=through_on,
        balances=balances,
        account_name_by_id=names,
        events=[
            _input_event(item, allocated_by_occurrence.get(item.id, Decimal(0)))
            for item in schedule.occurrences
        ],
        account_id=account_id,
        horizon=horizon,
        overdue_excluded_count=schedule.overdue_count,
        balance_mode=balance_mode,
    )


def build_fund_forecast(
    session: Session,
    *,
    today: date,
    horizon: ForecastHorizon,
) -> FundForecastResponse:
    through_on = horizon_end(today, horizon)
    schedule = forecast_schedule_snapshot(
        session,
        today=today,
        due_to=through_on,
        account_id=None,
    )
    # This follows the Scheduling -> Accounts -> Funds order used by the money
    # forecast and prevents a posting from appearing in current and planned data.
    list_account_identities(session, shared_lock=True)
    funds = locked_active_funds(session)
    mode = fund_allocation_mode(session)
    starting_reserve = sum(reserve_balances(session).values(), Decimal(0))
    projection = project_fund_allocations(funds, schedule.occurrences, mode)
    changes: dict[UUID, dict[date, Decimal]] = {fund.id: defaultdict(Decimal) for fund in funds}
    planned_transfer_total = Decimal(0)
    planned_allocation_total = Decimal(0)
    for event in projection.events:
        planned_transfer_total += event.incoming_amount
        for fund_id, amount in event.amounts.items():
            changes[fund_id][event.due_on] += amount
            planned_allocation_total += amount

    granularity = (
        ForecastGranularity.MONTH if horizon == ForecastHorizon.YEAR else ForecastGranularity.DAY
    )
    series: list[FundForecastSeriesResponse] = []
    for fund in funds:
        current = Decimal(fund.total_balance)
        starting = current
        points: list[FundForecastPointResponse] = []
        for period_from, on in _forecast_periods(today, through_on, granularity):
            change = sum(
                (
                    amount
                    for event_on, amount in changes[fund.id].items()
                    if period_from <= event_on <= on
                ),
                Decimal(0),
            )
            current += change
            points.append(
                FundForecastPointResponse(
                    period_from=period_from,
                    on=on,
                    change=_money(change),
                    balance=_money(current),
                )
            )
        series.append(
            FundForecastSeriesResponse(
                fund_id=fund.id,
                fund_name=fund.name,
                allocation_percentage=_money(
                    projection.starting_percentages.get(fund.id, Decimal(0))
                ),
                ending_allocation_percentage=_money(
                    projection.ending_percentages.get(fund.id, Decimal(0))
                ),
                starting_balance=_money(starting),
                ending_balance=_money(current),
                points=points,
            )
        )
    return FundForecastResponse(
        allocation_mode=mode,
        horizon=horizon,
        granularity=granularity,
        from_on=today,
        through_on=through_on,
        planned_transfer_total=_money(planned_transfer_total),
        planned_allocation_total=_money(planned_allocation_total),
        unallocated_total=_money(planned_transfer_total - planned_allocation_total),
        starting_reserve=_money(starting_reserve),
        ending_reserve=_money(
            starting_reserve
            + sum((event.reserve_amount for event in projection.events), Decimal(0))
        ),
        blocked_allocation_count=(
            0
            if mode == FundAllocationMode.DYNAMIC
            else sum(not event.amounts for event in projection.events)
        ),
        allocation_events=[
            FundForecastAllocationEventResponse(
                occurrence_id=event.occurrence_id,
                due_on=event.due_on,
                incoming_amount=_money(event.incoming_amount),
                allocated_amount=_money(sum(event.amounts.values(), Decimal(0))),
                reserve_amount=_money(event.reserve_amount),
                executable=bool(event.amounts) or mode == FundAllocationMode.DYNAMIC,
                allocations=[
                    FundForecastAllocationItemResponse(
                        fund_id=fund_id,
                        allocation_percentage=_money(event.percentages[fund_id]),
                        amount=_money(amount),
                    )
                    for fund_id, amount in sorted(event.amounts.items())
                ],
            )
            for event in projection.events
        ],
        series=series,
    )


def _scope_effect(
    event: ForecastInputEvent,
    account_id: UUID | None,
    balance_mode: ForecastBalanceMode,
) -> Decimal:
    if event.type == OperationType.INCOME:
        return event.amount if account_id in {None, event.account_id} else Decimal(0)
    if event.type == OperationType.EXPENSE:
        return -event.amount if account_id in {None, event.account_id} else Decimal(0)
    if account_id is None:
        return -event.allocated_to_funds if balance_mode == ForecastBalanceMode.FREE else Decimal(0)
    if account_id == event.account_id:
        return -event.amount
    if account_id == event.destination_account_id:
        return event.amount - (
            event.allocated_to_funds if balance_mode == ForecastBalanceMode.FREE else Decimal(0)
        )
    return Decimal(0)


def _input_event(
    item: PlannedOccurrence, allocated_to_funds: Decimal = Decimal(0)
) -> ForecastInputEvent:
    return ForecastInputEvent(
        occurrence_id=item.id,
        rule_id=item.rule_id,
        source_kind=item.source_kind,
        due_on=item.due_on,
        type=item.type,
        status=item.status,
        description=item.description,
        account_id=item.account_id,
        destination_account_id=item.destination_account_id,
        amount=item.amount,
        allocated_to_funds=allocated_to_funds,
    )


def _event_response(
    event: ForecastInputEvent, effect: Decimal, names: dict[UUID, str]
) -> ForecastEventResponse:
    return ForecastEventResponse(
        origin=event.origin,
        occurrence_id=event.occurrence_id,
        rule_id=event.rule_id,
        source_kind=event.source_kind,
        due_on=event.due_on,
        type=event.type,
        status=event.status,
        description=event.description,
        account_id=event.account_id,
        account_name=names[event.account_id],
        destination_account_id=event.destination_account_id,
        destination_account_name=(
            names[event.destination_account_id]
            if event.destination_account_id is not None
            else None
        ),
        amount=_money(event.amount),
        effect=_money(effect),
    )


def _money(value: Decimal) -> str:
    return format(value, "f")
