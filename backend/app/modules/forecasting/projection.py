"""Reusable exact projection over detached source data, with no persistence commands."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.accounts.contracts import AccountIdentity
from app.modules.forecasting.schemas import ForecastBalanceMode, ForecastHorizon, ForecastResponse
from app.modules.forecasting.service import (
    ForecastInputEvent,
    FundAllocationProjection,
    calculate_forecast,
    project_fund_allocations,
)
from app.modules.funds.contracts import FundResponse
from app.modules.scheduling.contracts import OccurrenceStatus, PlannedOccurrence
from app.modules.settings.contracts import FundAllocationMode


@dataclass(frozen=True, slots=True)
class ProjectionSnapshot:
    today: date
    through_on: date
    currency: str
    accounts: tuple[AccountIdentity, ...]
    balances: tuple[tuple[UUID, Decimal], ...]
    reserved: tuple[tuple[UUID, Decimal], ...]
    funds: tuple[FundResponse, ...]
    mode: FundAllocationMode
    occurrences: tuple[PlannedOccurrence, ...]
    overdue_count: int
    overdue_by_account: tuple[tuple[UUID, int], ...] = ()
    reserve_total: Decimal = Decimal(0)
    fund_positions: tuple[tuple[UUID, UUID, Decimal], ...] = ()
    reserve_by_account: tuple[tuple[UUID, Decimal], ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    free: ForecastResponse
    total: ForecastResponse
    funds: FundAllocationProjection


def project_snapshot(
    snapshot: ProjectionSnapshot,
    *,
    through_on: date,
    horizon: ForecastHorizon,
    account_id: UUID | None,
    occurrences: tuple[PlannedOccurrence, ...] | None = None,
    changed_id: UUID | None = None,
) -> ProjectionResult:
    """Both perspectives and funds use the same chronological event sequence."""
    selected = snapshot.occurrences if occurrences is None else occurrences
    events = [
        item
        for item in selected
        if snapshot.today <= item.due_on <= through_on
        and item.status in {OccurrenceStatus.PENDING, OccurrenceStatus.POSTPONED}
    ]
    allocation = project_fund_allocations(list(snapshot.funds), events, snapshot.mode)
    allocated = {
        item.occurrence_id: sum(item.amounts.values(), Decimal(0)) + item.reserve_amount
        for item in allocation.events
    }
    inputs = [
        ForecastInputEvent(
            occurrence_id=item.id,
            rule_id=item.rule_id,
            due_on=item.due_on,
            type=item.type,
            status=item.status,
            description=item.description,
            account_id=item.account_id,
            destination_account_id=item.destination_account_id,
            amount=item.amount,
            allocated_to_funds=allocated.get(item.id, Decimal(0)),
            source_kind=item.source_kind,
            origin="scenario" if item.id == changed_id else "plan",
        )
        for item in events
    ]
    balances, reserved = dict(snapshot.balances), dict(snapshot.reserved)
    names = {item.id: item.name for item in snapshot.accounts}
    overdue = (
        snapshot.overdue_count
        if account_id is None
        else dict(snapshot.overdue_by_account).get(account_id, 0)
    )

    def calculate(mode: ForecastBalanceMode) -> ForecastResponse:
        values = (
            balances
            if mode == ForecastBalanceMode.TOTAL
            else {key: value - reserved.get(key, Decimal(0)) for key, value in balances.items()}
        )
        return calculate_forecast(
            today=snapshot.today,
            through_on=through_on,
            balances=values,
            account_name_by_id=names,
            events=inputs,
            account_id=account_id,
            horizon=horizon,
            overdue_excluded_count=overdue,
            balance_mode=mode,
        )

    return ProjectionResult(
        calculate(ForecastBalanceMode.FREE), calculate(ForecastBalanceMode.TOTAL), allocation
    )
