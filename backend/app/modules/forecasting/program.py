"""Exact chronological cash/fund projection for composed financial scenarios."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.forecasting.projection import ProjectionResult, ProjectionSnapshot
from app.modules.forecasting.schemas import ForecastBalanceMode, ForecastHorizon, ForecastResponse
from app.modules.forecasting.service import (
    ForecastInputEvent,
    FundAllocationProjection,
    ProjectedAllocation,
    calculate_forecast,
)
from app.modules.funds.contracts import (
    FundDistributionState,
    dynamic_capacity_allocations,
    dynamic_percentages,
    percentage_allocations,
)
from app.modules.scheduling.contracts import OccurrenceStatus, PlannedOccurrence
from app.modules.settings.contracts import FundAllocationMode


@dataclass(frozen=True, slots=True)
class FundShortfall:
    event_id: UUID
    account_id: UUID
    fund_id: UUID
    on: date
    shortfall: Decimal


@dataclass(frozen=True, slots=True)
class ProgramResult:
    projection: ProjectionResult
    accounts: dict[UUID, tuple[ForecastResponse, ForecastResponse]]
    funding_issues: tuple[FundShortfall, ...]
    reserve_end: Decimal


def project_program(
    snapshot: ProjectionSnapshot,
    events: tuple[PlannedOccurrence, ...],
    *,
    horizon: ForecastHorizon,
    through_on: date,
    scope: UUID | None,
) -> ProgramResult:
    balances = {f.id: Decimal(f.total_balance) for f in snapshot.funds}
    starting = dict(balances)
    positions = {(f, a): v for f, a, v in snapshot.fund_positions}
    reserves = dict(snapshot.reserve_by_account)
    targets = {f.id: Decimal(f.target_amount) if f.target_amount else None for f in snapshot.funds}
    manual = [
        (f.id, Decimal(f.manual_allocation_percentage))
        for f in snapshot.funds
        if Decimal(f.manual_allocation_percentage) > 0
    ]
    dynamic = snapshot.mode == FundAllocationMode.DYNAMIC

    def states() -> list[FundDistributionState]:
        return [FundDistributionState(f.id, balances[f.id], targets[f.id]) for f in snapshot.funds]

    def shares() -> dict[UUID, Decimal]:
        return dict(dynamic_percentages(states()) if dynamic else manual)

    def refill() -> dict[UUID, Decimal]:
        if not dynamic:
            return {}
        allocations, _ = dynamic_capacity_allocations(sum(reserves.values(), Decimal(0)), states())
        moved: dict[UUID, Decimal] = {}
        for part in allocations:
            remaining = part.amount
            for account in sorted(reserves):
                value = min(remaining, reserves[account])
                positions[part.fund_id, account] = (
                    positions.get((part.fund_id, account), Decimal(0)) + value
                )
                reserves[account] -= value
                balances[part.fund_id] += value
                remaining -= value
            moved[part.fund_id] = part.amount
        return moved

    beginning_shares = shares()
    inputs: list[ForecastInputEvent] = []
    allocations: list[ProjectedAllocation] = []
    issues: list[FundShortfall] = []
    for event in sorted(events, key=lambda item: (item.due_on, item.id)):
        if not snapshot.today <= event.due_on <= through_on or event.status not in {
            OccurrenceStatus.PENDING,
            OccurrenceStatus.POSTPONED,
        }:
            continue
        adjustments: dict[UUID, Decimal] = defaultdict(Decimal)
        changes: dict[UUID, Decimal] = defaultdict(Decimal)
        before_reserve = sum(reserves.values(), Decimal(0))
        percentages = shares()
        if event.fund_id is not None:
            key = (event.fund_id, event.account_id)
            available = positions.get(key, Decimal(0))
            covered = min(event.amount, available)
            if covered < event.amount:
                issues.append(
                    FundShortfall(
                        event.id,
                        event.account_id,
                        event.fund_id,
                        event.due_on,
                        event.amount - covered,
                    )
                )
            positions[key] = available - covered
            balances[event.fund_id] -= covered
            changes[event.fund_id] -= covered
            adjustments[event.account_id] += covered
            for fund, value in refill().items():
                changes[fund] += value
        if event.allocate_to_funds:
            assert event.destination_account_id is not None
            if dynamic:
                parts, overflow = dynamic_capacity_allocations(event.amount, states())
            else:
                parts, overflow = percentage_allocations(event.amount, manual), Decimal(0)
            for part in parts:
                balances[part.fund_id] += part.amount
                key = (part.fund_id, event.destination_account_id)
                positions[key] = positions.get(key, Decimal(0)) + part.amount
                changes[part.fund_id] += part.amount
                adjustments[event.destination_account_id] -= part.amount
            reserves[event.destination_account_id] = (
                reserves.get(event.destination_account_id, Decimal(0)) + overflow
            )
            adjustments[event.destination_account_id] -= overflow
        if changes or sum(reserves.values(), Decimal(0)) != before_reserve:
            allocations.append(
                ProjectedAllocation(
                    event.id,
                    event.due_on,
                    event.amount,
                    percentages,
                    dict(changes),
                    sum(reserves.values(), Decimal(0)) - before_reserve,
                )
            )
        inputs.append(
            ForecastInputEvent(
                occurrence_id=event.id,
                rule_id=event.rule_id,
                source_kind=event.source_kind,
                due_on=event.due_on,
                type=event.type,
                status=event.status,
                description=event.description,
                account_id=event.account_id,
                destination_account_id=event.destination_account_id,
                amount=event.amount,
                origin=event.origin,
                free_adjustments=tuple(sorted(adjustments.items())),
            )
        )
    names = {a.id: a.name for a in snapshot.accounts}
    physical, reserved = dict(snapshot.balances), dict(snapshot.reserved)

    def calculate(mode: ForecastBalanceMode, account: UUID | None) -> ForecastResponse:
        values = (
            physical
            if mode == ForecastBalanceMode.TOTAL
            else {a: b - reserved.get(a, Decimal(0)) for a, b in physical.items()}
        )
        return calculate_forecast(
            today=snapshot.today,
            through_on=through_on,
            balances=values,
            account_name_by_id=names,
            events=inputs,
            account_id=account,
            horizon=horizon,
            balance_mode=mode,
            overdue_excluded_count=snapshot.overdue_count
            if account is None
            else dict(snapshot.overdue_by_account).get(account, 0),
        )

    accounts = {
        a.id: (
            calculate(ForecastBalanceMode.FREE, a.id),
            calculate(ForecastBalanceMode.TOTAL, a.id),
        )
        for a in snapshot.accounts
    }
    free, total = (
        accounts[scope]
        if scope is not None
        else (calculate(ForecastBalanceMode.FREE, None), calculate(ForecastBalanceMode.TOTAL, None))
    )
    allocation = FundAllocationProjection(
        snapshot.mode, starting, balances, beginning_shares, shares(), allocations
    )
    return ProgramResult(
        ProjectionResult(free, total, allocation),
        accounts,
        tuple(issues),
        sum(reserves.values(), Decimal(0)),
    )
