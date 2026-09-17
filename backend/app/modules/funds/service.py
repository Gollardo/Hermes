from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.modules.accounts.contracts import account_names, list_account_identities
from app.modules.funds.models import (
    Fund,
    FundEvent,
    FundEventType,
    FundMovement,
    FundReserveMovement,
)
from app.modules.funds.schemas import (
    AccountCoverageResponse,
    AllocationCreateRequest,
    AllocationItem,
    AllocationPreviewResponse,
    FundEventResponse,
    FundMovementResponse,
    FundPositionResponse,
    FundReleaseRequest,
    FundReserveMovementResponse,
    FundReserveReleaseRequest,
    FundResponse,
    FundSummaryResponse,
    FundTransferCreateRequest,
    FundUpdateRequest,
    RedistributionCreateRequest,
)
from app.modules.settings.contracts import (
    FundAllocationMode,
    application_timezone,
    fund_allocation_mode,
)

MONEY_QUANTUM = Decimal("0.0001")
PERCENTAGE_QUANTUM = Decimal("0.0001")
MIN_DYNAMIC_PERCENTAGE = Decimal("5")
FUND_DEFINITION_LOCK = 4_621_083_119
LEGACY_TRANSFER_ALLOCATION_WINDOW = timedelta(seconds=1)


class FundNotFoundError(RuntimeError):
    pass


class FundConflictError(RuntimeError):
    pass


class FundPercentageLimitError(RuntimeError):
    pass


class FundBalanceError(RuntimeError):
    pass


class FundCoverageError(RuntimeError):
    pass


class FundAllocationUnavailableError(RuntimeError):
    pass


class FundArchiveBalanceError(RuntimeError):
    pass


class FundArchivedMutationError(RuntimeError):
    pass


class DynamicFundTargetsRequiredError(RuntimeError):
    pass


class FundReserveBalanceError(RuntimeError):
    pass


class FundTargetCapacityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LegacyTransferAllocationMatch:
    """Narrow fingerprint for allocation pairs written before their causal link existed."""

    occurred_on: date
    description: str | None
    operation_created_at: datetime
    destination_account_id: UUID
    amount: Decimal


@dataclass(frozen=True, slots=True)
class FundDistributionState:
    fund_id: UUID
    balance: Decimal
    target_amount: Decimal | None


@dataclass(frozen=True, slots=True)
class LockedDistributionSnapshot:
    mode: FundAllocationMode
    funds: list[Fund]
    balances: dict[UUID, Decimal]
    percentages: list[tuple[UUID, Decimal]]


def _lock_definitions(session: Session, *, shared: bool = False) -> None:
    function = "pg_advisory_xact_lock_shared" if shared else "pg_advisory_xact_lock"
    session.execute(text(f"SELECT {function}(:key)"), {"key": FUND_DEFINITION_LOCK})


def _get_fund(session: Session, fund_id: UUID, *, lock: bool = False) -> Fund:
    query = select(Fund).where(Fund.id == fund_id)
    if lock:
        query = query.with_for_update()
    fund = session.scalar(query)
    if fund is None:
        raise FundNotFoundError
    return fund


def _percentage_total(session: Session, *, excluding: UUID | None = None) -> Decimal:
    conditions: list[ColumnElement[bool]] = [Fund.archived_at.is_(None)]
    if excluding is not None:
        conditions.append(Fund.id != excluding)
    value = session.scalar(
        select(func.coalesce(func.sum(Fund.allocation_percentage), 0)).where(*conditions)
    )
    return Decimal(value or 0)


def _check_percentage(session: Session, value: Decimal, *, excluding: UUID | None = None) -> None:
    if _percentage_total(session, excluding=excluding) + value > 100:
        raise FundPercentageLimitError


def dynamic_percentages(states: list[FundDistributionState]) -> list[tuple[UUID, Decimal]]:
    """Calculate exact percentages from each incomplete fund's relative target gap."""
    active = [
        state
        for state in states
        if state.target_amount is not None and state.balance < state.target_amount
    ]
    if not active:
        return []
    relative_gaps = {
        state.fund_id: (state.target_amount - state.balance) / state.target_amount
        for state in active
        if state.target_amount is not None
    }
    total_relative_gap = sum(relative_gaps.values(), Decimal(0))
    count = Decimal(len(active))
    base = min(MIN_DYNAMIC_PERCENTAGE, Decimal(100) / count)
    dynamic_pool = Decimal(100) - count * base
    raw = {
        state.fund_id: base + dynamic_pool * relative_gaps[state.fund_id] / total_relative_gap
        for state in active
    }
    rounded = {
        fund_id: percentage.quantize(PERCENTAGE_QUANTUM, rounding=ROUND_DOWN)
        for fund_id, percentage in raw.items()
    }
    units = int((Decimal(100) - sum(rounded.values(), Decimal(0))) / PERCENTAGE_QUANTUM)
    order = sorted(raw, key=lambda fund_id: (-(raw[fund_id] - rounded[fund_id]), fund_id))
    for fund_id in order[:units]:
        rounded[fund_id] += PERCENTAGE_QUANTUM
    return [(fund_id, rounded[fund_id]) for fund_id in sorted(rounded)]


def complete_percentage_allocations(
    amount: Decimal, percentages: list[tuple[UUID, Decimal]]
) -> list[AllocationItem]:
    """Allocate the complete exact amount using deterministic largest remainders."""
    if not percentages:
        return []
    raw = {fund_id: amount * percentage / 100 for fund_id, percentage in percentages}
    rounded = {
        fund_id: value.quantize(MONEY_QUANTUM, rounding=ROUND_DOWN)
        for fund_id, value in raw.items()
    }
    units = int((amount - sum(rounded.values(), Decimal(0))) / MONEY_QUANTUM)
    order = sorted(raw, key=lambda fund_id: (-(raw[fund_id] - rounded[fund_id]), fund_id))
    for fund_id in order[:units]:
        rounded[fund_id] += MONEY_QUANTUM
    return [AllocationItem(fund_id=fund_id, amount=rounded[fund_id]) for fund_id in sorted(rounded)]


def dynamic_capacity_allocations(
    amount: Decimal, states: list[FundDistributionState]
) -> tuple[list[AllocationItem], Decimal]:
    """Distribute exactly up to targets and return the amount left for reserve."""
    balances = {state.fund_id: state.balance for state in states}
    targets = {
        state.fund_id: state.target_amount for state in states if state.target_amount is not None
    }
    allocated = dict.fromkeys(balances, Decimal(0))
    remaining = amount
    while remaining > 0:
        percentages = dynamic_percentages(
            [
                FundDistributionState(fund_id, balances[fund_id], targets.get(fund_id))
                for fund_id in sorted(balances)
            ]
        )
        if not percentages:
            break
        proposed = complete_percentage_allocations(remaining, percentages)
        accepted = Decimal(0)
        for item in proposed:
            target = targets[item.fund_id]
            assert target is not None
            value = min(item.amount, target - balances[item.fund_id])
            if value <= 0:
                continue
            balances[item.fund_id] += value
            allocated[item.fund_id] += value
            accepted += value
        if accepted == 0:
            break
        remaining -= accepted
    return (
        [
            AllocationItem(fund_id=fund_id, amount=value)
            for fund_id, value in sorted(allocated.items())
            if value > 0
        ],
        remaining,
    )


def _fund_balances(session: Session, fund_ids: set[UUID]) -> dict[UUID, Decimal]:
    balances = dict.fromkeys(fund_ids, Decimal(0))
    if not fund_ids:
        return balances
    rows = session.execute(
        select(FundMovement.fund_id, func.coalesce(func.sum(FundMovement.amount), 0))
        .where(FundMovement.fund_id.in_(fund_ids))
        .group_by(FundMovement.fund_id)
    )
    for fund_id, value in rows:
        balances[fund_id] = Decimal(value or 0)
    return balances


def _percentages_for(
    mode: FundAllocationMode, funds: list[Fund], balances: dict[UUID, Decimal]
) -> list[tuple[UUID, Decimal]]:
    if mode == FundAllocationMode.MANUAL:
        return [
            (fund.id, Decimal(fund.allocation_percentage))
            for fund in sorted(funds, key=lambda item: item.id)
            if Decimal(fund.allocation_percentage) > 0
        ]
    if any(fund.target_amount is None for fund in funds):
        raise DynamicFundTargetsRequiredError
    return dynamic_percentages(
        [
            FundDistributionState(
                fund_id=fund.id,
                balance=balances[fund.id],
                target_amount=fund.target_amount,
            )
            for fund in funds
        ]
    )


def locked_distribution_snapshot(session: Session, *, shared: bool) -> LockedDistributionSnapshot:
    _lock_definitions(session, shared=shared)
    query = (
        select(Fund)
        .where(Fund.archived_at.is_(None))
        .order_by(Fund.id)
        .with_for_update(read=shared)
    )
    funds = list(session.scalars(query).all())
    balances = _fund_balances(session, {fund.id for fund in funds})
    mode = fund_allocation_mode(session)
    return LockedDistributionSnapshot(
        mode=mode,
        funds=funds,
        balances=balances,
        percentages=_percentages_for(mode, funds, balances),
    )


def validate_dynamic_targets(session: Session) -> None:
    _lock_definitions(session)
    missing = session.scalar(
        select(Fund.id).where(Fund.archived_at.is_(None), Fund.target_amount.is_(None)).limit(1)
    )
    if missing is not None:
        raise DynamicFundTargetsRequiredError


def snapshot_dynamic_percentages_as_manual(session: Session) -> None:
    """Freeze current derived values, including zero for filled and archived funds."""
    _lock_definitions(session)
    funds = list(session.scalars(select(Fund).order_by(Fund.id).with_for_update()).all())
    active = [fund for fund in funds if fund.archived_at is None]
    balances = _fund_balances(session, {fund.id for fund in active})
    if any(fund.target_amount is None for fund in active):
        raise DynamicFundTargetsRequiredError
    percentages = dict(_percentages_for(FundAllocationMode.DYNAMIC, active, balances))
    now = datetime.now(UTC)
    for fund in funds:
        value = percentages.get(fund.id, Decimal(0))
        if Decimal(fund.allocation_percentage) == value:
            continue
        fund.allocation_percentage = value
        fund.updated_at = now
        fund.version += 1
    session.flush()


def create_fund(
    session: Session,
    *,
    name: str,
    description: str | None,
    percentage: Decimal,
    target_amount: Decimal | None,
) -> Fund:
    _lock_definitions(session)
    mode = fund_allocation_mode(session)
    if mode == FundAllocationMode.DYNAMIC and target_amount is None:
        raise DynamicFundTargetsRequiredError
    if mode == FundAllocationMode.MANUAL:
        _check_percentage(session, percentage)
    now = datetime.now(UTC)
    fund = Fund(
        name=name,
        description=description,
        allocation_percentage=percentage,
        target_amount=target_amount,
        created_at=now,
        updated_at=now,
        version=1,
    )
    session.add(fund)
    session.flush()
    return fund


def update_fund(session: Session, fund_id: UUID, payload: FundUpdateRequest) -> Fund:
    _lock_definitions(session)
    fund = _get_fund(session, fund_id, lock=True)
    if fund.version != payload.version:
        raise FundConflictError
    if fund.archived_at is None:
        mode = fund_allocation_mode(session)
        if mode == FundAllocationMode.DYNAMIC and payload.target_amount is None:
            raise DynamicFundTargetsRequiredError
        if mode == FundAllocationMode.MANUAL:
            _check_percentage(session, payload.allocation_percentage, excluding=fund.id)
    fund.name = payload.name
    fund.description = payload.description
    fund.allocation_percentage = payload.allocation_percentage
    fund.target_amount = payload.target_amount
    fund.updated_at = datetime.now(UTC)
    fund.version += 1
    session.flush()
    return fund


def fund_balance(session: Session, fund_id: UUID, account_id: UUID | None = None) -> Decimal:
    conditions = [FundMovement.fund_id == fund_id]
    if account_id is not None:
        conditions.append(FundMovement.account_id == account_id)
    value = session.scalar(
        select(func.coalesce(func.sum(FundMovement.amount), 0)).where(*conditions)
    )
    return Decimal(value or 0)


def reserved_balance(session: Session, account_id: UUID) -> Decimal:
    fund_value = session.scalar(
        select(func.coalesce(func.sum(FundMovement.amount), 0)).where(
            FundMovement.account_id == account_id
        )
    )
    return Decimal(fund_value or 0) + reserve_balance(session, account_id)


def reserve_balance(session: Session, account_id: UUID | None = None) -> Decimal:
    conditions = []
    if account_id is not None:
        conditions.append(FundReserveMovement.account_id == account_id)
    value = session.scalar(
        select(func.coalesce(func.sum(FundReserveMovement.amount), 0)).where(*conditions)
    )
    return Decimal(value or 0)


def reserve_balances(session: Session) -> dict[UUID, Decimal]:
    return {
        account_id: Decimal(value)
        for account_id, value in session.execute(
            select(
                FundReserveMovement.account_id,
                func.sum(FundReserveMovement.amount),
            )
            .group_by(FundReserveMovement.account_id)
            .having(func.sum(FundReserveMovement.amount) > 0)
            .order_by(FundReserveMovement.account_id)
        )
    }


def reserved_balances(session: Session, account_ids: set[UUID]) -> dict[UUID, Decimal]:
    """Return exact per-account reserves in one Funds-owned aggregate read."""
    balances = dict.fromkeys(account_ids, Decimal(0))
    if not account_ids:
        return balances
    rows = session.execute(
        select(FundMovement.account_id, func.coalesce(func.sum(FundMovement.amount), 0))
        .where(FundMovement.account_id.in_(account_ids))
        .group_by(FundMovement.account_id)
    )
    for account_id, value in rows:
        balances[account_id] = Decimal(value or 0)
    for account_id, value in reserve_balances(session).items():
        if account_id in balances:
            balances[account_id] += value
    return balances


def account_has_fund_history(session: Session, account_id: UUID) -> bool:
    return (
        session.scalar(
            select(FundMovement.id).where(FundMovement.account_id == account_id).limit(1)
        )
        is not None
        or session.scalar(
            select(FundReserveMovement.id)
            .where(FundReserveMovement.account_id == account_id)
            .limit(1)
        )
        is not None
    )


def archive_fund(
    session: Session,
    fund_id: UUID,
    *,
    restore: bool,
    expected_version: int,
) -> Fund:
    _lock_definitions(session)
    fund = _get_fund(session, fund_id, lock=True)
    if fund.version != expected_version:
        raise FundConflictError
    if restore:
        if fund.archived_at is None:
            return fund
        mode = fund_allocation_mode(session)
        if mode == FundAllocationMode.DYNAMIC and fund.target_amount is None:
            raise DynamicFundTargetsRequiredError
        if mode == FundAllocationMode.MANUAL:
            _check_percentage(session, fund.allocation_percentage)
        fund.archived_at = None
    else:
        if fund.archived_at is not None:
            return fund
        if fund_balance(session, fund.id) != 0:
            raise FundArchiveBalanceError
        fund.archived_at = datetime.now(UTC)
    fund.updated_at = datetime.now(UTC)
    fund.version += 1
    session.flush()
    return fund


def _fund_response(
    session: Session,
    fund: Fund,
    *,
    balance: Decimal | None = None,
    effective_percentage: Decimal | None = None,
    mode: FundAllocationMode | None = None,
) -> FundResponse:
    balance = fund_balance(session, fund.id) if balance is None else balance
    mode = fund_allocation_mode(session) if mode is None else mode
    if fund.archived_at is not None:
        effective_percentage = Decimal(0)
        status = "archived"
    elif mode == FundAllocationMode.MANUAL:
        effective_percentage = Decimal(fund.allocation_percentage)
        status = "manual"
    elif fund.target_amount is not None and balance >= fund.target_amount:
        effective_percentage = Decimal(0)
        status = "filled"
    else:
        effective_percentage = effective_percentage or Decimal(0)
        status = "active"
    progress = balance * 100 / fund.target_amount if fund.target_amount is not None else None
    remaining = (
        max(fund.target_amount - balance, Decimal(0)) if fund.target_amount is not None else None
    )
    return FundResponse(
        id=fund.id,
        name=fund.name,
        description=fund.description,
        allocation_percentage=format(effective_percentage, "f"),
        manual_allocation_percentage=format(fund.allocation_percentage, "f"),
        allocation_mode=mode,
        target_amount=format(fund.target_amount, "f") if fund.target_amount is not None else None,
        total_balance=format(balance, "f"),
        remaining_amount=format(remaining, "f") if remaining is not None else None,
        distribution_status=status,
        progress_percentage=format(progress, ".2f") if progress is not None else None,
        archived=fund.archived_at is not None,
        version=fund.version,
        created_at=fund.created_at,
        updated_at=fund.updated_at,
    )


def list_funds(session: Session, *, include_archived: bool = True) -> list[FundResponse]:
    _lock_definitions(session, shared=True)
    query = select(Fund)
    if not include_archived:
        query = query.where(Fund.archived_at.is_(None))
    funds = list(
        session.scalars(
            query.order_by(Fund.archived_at.nulls_first(), Fund.name, Fund.id).with_for_update(
                read=True
            )
        ).all()
    )
    balances = _fund_balances(session, {fund.id for fund in funds})
    mode = fund_allocation_mode(session)
    active = [fund for fund in funds if fund.archived_at is None]
    percentages = dict(_percentages_for(mode, active, balances))
    return [
        _fund_response(
            session,
            fund,
            balance=balances[fund.id],
            effective_percentage=percentages.get(fund.id, Decimal(0)),
            mode=mode,
        )
        for fund in funds
    ]


def locked_active_funds(session: Session) -> list[FundResponse]:
    """Return one active definition/balance snapshot for cross-module projections."""
    snapshot = locked_distribution_snapshot(session, shared=True)
    percentages = dict(snapshot.percentages)
    return [
        _fund_response(
            session,
            fund,
            balance=snapshot.balances[fund.id],
            effective_percentage=percentages.get(fund.id, Decimal(0)),
            mode=snapshot.mode,
        )
        for fund in sorted(snapshot.funds, key=lambda item: (item.name, item.id))
    ]


def locked_percentage_definitions(session: Session) -> list[tuple[UUID, Decimal]]:
    """Return one locked mode-aware percentage snapshot."""
    return locked_distribution_snapshot(session, shared=True).percentages


def get_fund_response(session: Session, fund_id: UUID) -> FundResponse:
    response = next((item for item in list_funds(session) if item.id == fund_id), None)
    if response is None:
        raise FundNotFoundError
    return response


def validate_account_coverage(session: Session, physical_balances: dict[UUID, Decimal]) -> None:
    for account_id, physical in physical_balances.items():
        reserved = reserved_balance(session, account_id)
        if reserved < 0 or reserved > physical:
            raise FundCoverageError
        rows = session.execute(
            select(FundMovement.fund_id, func.sum(FundMovement.amount))
            .where(FundMovement.account_id == account_id)
            .group_by(FundMovement.fund_id)
        )
        if any(Decimal(value) < 0 for _, value in rows):
            raise FundBalanceError
        if reserve_balance(session, account_id) < 0:
            raise FundReserveBalanceError


def summary_with_physical_balances(
    session: Session, physical_balances: dict[UUID, Decimal]
) -> FundSummaryResponse:
    funds = list_funds(session)
    position_rows = session.execute(
        select(FundMovement.fund_id, FundMovement.account_id, func.sum(FundMovement.amount))
        .group_by(FundMovement.fund_id, FundMovement.account_id)
        .having(func.sum(FundMovement.amount) != 0)
    ).all()
    fund_names = {fund.id: fund.name for fund in session.scalars(select(Fund)).all()}
    account_ids = {account_id for _, account_id, _ in position_rows}
    account_ids.update(
        account_id for (account_id,) in session.execute(select(FundMovement.account_id).distinct())
    )
    names = account_names(session, account_ids) if account_ids else {}
    positions = [
        FundPositionResponse(
            fund_id=fund_id,
            fund_name=fund_names[fund_id],
            account_id=account_id,
            account_name=names[account_id],
            balance=format(Decimal(value), "f"),
        )
        for fund_id, account_id, value in position_rows
    ]
    accounts = list_account_identities(session)
    coverage: list[AccountCoverageResponse] = []
    for account in accounts:
        physical = physical_balances[account.id]
        fund_reserved = reserved_balance(session, account.id) - reserve_balance(session, account.id)
        reserve = reserve_balance(session, account.id)
        reserved = reserved_balance(session, account.id)
        coverage.append(
            AccountCoverageResponse(
                account_id=account.id,
                account_name=account.name,
                physical_balance=format(physical, "f"),
                reserved_balance=format(reserved, "f"),
                fund_reserved_balance=format(fund_reserved, "f"),
                reserve_balance=format(reserve, "f"),
                free_balance=format(physical - reserved, "f"),
                archived=account.archived,
            )
        )
    mode = fund_allocation_mode(session)
    return FundSummaryResponse(
        funds=funds,
        positions=positions,
        accounts=coverage,
        active_percentage=format(
            sum(
                (Decimal(fund.allocation_percentage) for fund in funds if not fund.archived),
                Decimal(0),
            ),
            "f",
        ),
        allocation_mode=mode,
        total_reserved=format(
            sum((Decimal(f.total_balance) for f in funds), Decimal(0)) + reserve_balance(session),
            "f",
        ),
        total_fund_reserved=format(sum((Decimal(f.total_balance) for f in funds), Decimal(0)), "f"),
        total_reserve=format(reserve_balance(session), "f"),
        total_free=format(sum((Decimal(a.free_balance) for a in coverage), Decimal(0)), "f"),
    )


def percentage_allocations(
    amount: Decimal, percentages: list[tuple[UUID, Decimal]]
) -> list[AllocationItem]:
    """Apply the documented independent round-down rule without float arithmetic."""
    return [
        AllocationItem(
            fund_id=fund_id,
            amount=(amount * percentage / 100).quantize(MONEY_QUANTUM, rounding=ROUND_DOWN),
        )
        for fund_id, percentage in percentages
    ]


def allocation_preview_with_free_balance(
    session: Session, account_id: UUID, amount: Decimal, free: Decimal
) -> AllocationPreviewResponse:
    snapshot = locked_distribution_snapshot(session, shared=False)
    reserve_amount = Decimal(0)
    if snapshot.mode == FundAllocationMode.DYNAMIC:
        allocations, reserve_amount = dynamic_capacity_allocations(
            amount,
            [
                FundDistributionState(fund.id, snapshot.balances[fund.id], fund.target_amount)
                for fund in snapshot.funds
            ],
        )
    else:
        allocations = percentage_allocations(amount, snapshot.percentages)
    percentage_by_fund = dict(snapshot.percentages)
    allocations = [
        item.model_copy(
            update={"allocation_percentage": format(percentage_by_fund[item.fund_id], "f")}
        )
        for item in allocations
    ]
    allocated = sum((item.amount for item in allocations), Decimal(0))
    return AllocationPreviewResponse(
        account_id=account_id,
        amount=format(amount, "f"),
        allocations=allocations,
        allocated_amount=format(allocated, "f"),
        unallocated_amount=format(
            (
                amount - allocated - reserve_amount
                if snapshot.mode == FundAllocationMode.DYNAMIC
                else amount - allocated
            ),
            "f",
        ),
        reserve_amount=format(reserve_amount, "f"),
        free_before=format(free, "f"),
        free_after=format(free - allocated - reserve_amount, "f"),
    )


def locked_percentage_allocation_preview_with_free_balance(
    session: Session, account_id: UUID, amount: Decimal, free: Decimal
) -> AllocationPreviewResponse:
    """Read one percentage snapshot protected from concurrent fund-definition changes."""
    return allocation_preview_with_free_balance(session, account_id, amount, free)


def create_allocation_with_free_balance(
    session: Session,
    payload: AllocationCreateRequest,
    free: Decimal,
    *,
    caused_by_operation_id: UUID | None = None,
) -> FundEvent:
    funds = _lock_fund_references(session, {item.fund_id for item in payload.allocations})
    if any(fund.archived_at is not None for fund in funds.values()):
        raise FundNotFoundError
    allocated = sum((item.amount for item in payload.allocations), Decimal(0))
    mode = fund_allocation_mode(session)
    if mode == FundAllocationMode.DYNAMIC:
        balances = _fund_balances(session, set(funds))
        if any(
            fund.target_amount is None
            or balances[fund_id]
            + sum(
                (item.amount for item in payload.allocations if item.fund_id == fund_id),
                Decimal(0),
            )
            > fund.target_amount
            for fund_id, fund in funds.items()
        ):
            raise FundTargetCapacityError
    if mode == FundAllocationMode.MANUAL and allocated <= 0:
        raise FundAllocationUnavailableError
    reserve_amount = (
        payload.amount - allocated if mode == FundAllocationMode.DYNAMIC else Decimal(0)
    )
    reserved = allocated + reserve_amount
    if allocated > payload.amount or reserved > free:
        raise FundCoverageError
    event = _event(
        session,
        FundEventType.ALLOCATION,
        payload.occurred_on,
        payload.description,
        caused_by_operation_id=caused_by_operation_id,
    )
    _add_fund_movements(
        session,
        [
            FundMovement(
                fund_id=item.fund_id,
                account_id=payload.account_id,
                event_id=event.id,
                operation_id=None,
                amount=item.amount,
            )
            for item in payload.allocations
            if item.amount != 0
        ],
    )
    if reserve_amount > 0:
        session.add(
            FundReserveMovement(
                account_id=payload.account_id,
                event_id=event.id,
                amount=reserve_amount,
            )
        )
    session.flush()
    return event


def remove_operation_reserve_distributions(session: Session, operation_id: UUID) -> None:
    events = list(
        session.scalars(
            select(FundEvent)
            .where(
                FundEvent.caused_by_operation_id == operation_id,
                FundEvent.type == FundEventType.RESERVE_DISTRIBUTION,
            )
            .with_for_update()
        ).all()
    )
    for event in events:
        session.delete(event)
    session.flush()


def lock_operation_dependent_allocation(
    session: Session,
    operation_id: UUID,
    *,
    legacy_transfer_allocation: LegacyTransferAllocationMatch | None = None,
) -> bool:
    """Protect the immutable allocation paired with a composed transfer update."""
    linked_event_id = session.scalar(
        select(FundEvent.id)
        .where(
            FundEvent.caused_by_operation_id == operation_id,
            FundEvent.type == FundEventType.ALLOCATION,
        )
        .with_for_update()
    )
    return linked_event_id is not None or (
        legacy_transfer_allocation is not None
        and bool(_legacy_transfer_allocation_events(session, legacy_transfer_allocation))
    )


def _legacy_transfer_allocation_events(
    session: Session, match: LegacyTransferAllocationMatch
) -> list[FundEvent]:
    candidates = list(
        session.scalars(
            select(FundEvent)
            .where(
                FundEvent.caused_by_operation_id.is_(None),
                FundEvent.type == FundEventType.ALLOCATION,
                FundEvent.occurred_on == match.occurred_on,
                FundEvent.description.is_not_distinct_from(match.description),
                FundEvent.created_at >= match.operation_created_at,
                FundEvent.created_at
                <= match.operation_created_at + LEGACY_TRANSFER_ALLOCATION_WINDOW,
            )
            .with_for_update()
        ).all()
    )
    return [
        event for event in candidates if _matches_legacy_transfer_allocation(session, event, match)
    ]


def remove_operation_dependent_events(
    session: Session,
    operation_id: UUID,
    *,
    legacy_transfer_allocation: LegacyTransferAllocationMatch | None = None,
) -> None:
    """Remove Funds events which must disappear with an operation deletion.

    New transfer-and-allocation pairs use ``caused_by_operation_id``.  The
    constrained fallback is solely for pairs created before that link was
    recorded: it accepts exactly one immediately-following, same-payload
    allocation on the destination account and never guesses among candidates.
    """
    events = list(
        session.scalars(
            select(FundEvent)
            .where(FundEvent.caused_by_operation_id == operation_id)
            .with_for_update()
        ).all()
    )
    if legacy_transfer_allocation is not None:
        matched = _legacy_transfer_allocation_events(session, legacy_transfer_allocation)
        if len(matched) == 1:
            events.append(matched[0])
    fund_ids = set(
        session.scalars(
            select(FundMovement.fund_id).where(
                FundMovement.event_id.in_([event.id for event in events])
            )
        ).all()
    )
    funds = _lock_fund_references(session, fund_ids)
    for event in events:
        session.delete(event)
    session.flush()
    if any(
        fund.archived_at is not None and fund_balance(session, fund.id) != 0
        for fund in funds.values()
    ):
        raise FundArchivedMutationError


def _matches_legacy_transfer_allocation(
    session: Session, event: FundEvent, match: LegacyTransferAllocationMatch
) -> bool:
    fund_movements = list(
        session.execute(
            select(FundMovement.account_id, FundMovement.amount).where(
                FundMovement.event_id == event.id
            )
        )
    )
    reserve_movements = list(
        session.execute(
            select(FundReserveMovement.account_id, FundReserveMovement.amount).where(
                FundReserveMovement.event_id == event.id
            )
        )
    )
    movements = fund_movements + reserve_movements
    return (
        bool(movements)
        and all(
            account_id == match.destination_account_id and amount > 0
            for account_id, amount in movements
        )
        and sum((Decimal(amount) for _, amount in movements), Decimal(0)) <= match.amount
    )


def rebalance_reserve(
    session: Session,
    *,
    occurred_on: date | None = None,
    caused_by_operation_id: UUID | None = None,
) -> FundEvent | None:
    """Assign every available account reserve to incomplete funds without moving cash."""
    if fund_allocation_mode(session) != FundAllocationMode.DYNAMIC:
        return None
    occurred_on = occurred_on or datetime.now(ZoneInfo(application_timezone(session))).date()
    snapshot = locked_distribution_snapshot(session, shared=False)
    by_account = reserve_balances(session)
    total = sum(by_account.values(), Decimal(0))
    if total <= 0:
        return None
    allocations, _ = dynamic_capacity_allocations(
        total,
        [
            FundDistributionState(fund.id, snapshot.balances[fund.id], fund.target_amount)
            for fund in snapshot.funds
        ],
    )
    if not allocations:
        return None
    event = _event(
        session,
        FundEventType.RESERVE_DISTRIBUTION,
        occurred_on,
        None,
        caused_by_operation_id=caused_by_operation_id,
    )
    account_remaining = dict(by_account)
    reserve_used = dict.fromkeys(by_account, Decimal(0))
    fund_movements: list[FundMovement] = []
    for allocation in allocations:
        remaining = allocation.amount
        for account_id in sorted(account_remaining):
            value = min(remaining, account_remaining[account_id])
            if value <= 0:
                continue
            fund_movements.append(
                FundMovement(
                    fund_id=allocation.fund_id,
                    account_id=account_id,
                    operation_id=None,
                    event_id=event.id,
                    amount=value,
                )
            )
            account_remaining[account_id] -= value
            reserve_used[account_id] += value
            remaining -= value
            if remaining == 0:
                break
        assert remaining == 0
    _add_fund_movements(session, fund_movements)
    session.add_all(
        FundReserveMovement(account_id=account_id, event_id=event.id, amount=-value)
        for account_id, value in reserve_used.items()
        if value > 0
    )
    session.flush()
    return event


def release_reserve(session: Session, payload: FundReserveReleaseRequest) -> FundEvent:
    _lock_definitions(session)
    if reserve_balance(session, payload.account_id) < payload.amount:
        raise FundReserveBalanceError
    event = _event(
        session,
        FundEventType.RESERVE_RELEASE,
        payload.occurred_on,
        payload.description,
    )
    session.add(
        FundReserveMovement(
            account_id=payload.account_id,
            event_id=event.id,
            amount=-payload.amount,
        )
    )
    session.flush()
    return event


def create_redistribution_with_physical_balances(
    session: Session,
    payload: RedistributionCreateRequest,
    physical_balances: dict[UUID, Decimal],
) -> FundEvent:
    fund = _lock_fund_references(session, {payload.fund_id})[payload.fund_id]
    if fund.archived_at is not None:
        raise FundNotFoundError
    event = _event(session, FundEventType.REDISTRIBUTION, payload.occurred_on, payload.description)
    _add_fund_movements(
        session,
        [
            FundMovement(
                fund_id=fund.id,
                account_id=payload.source_account_id,
                event_id=event.id,
                operation_id=None,
                amount=-payload.amount,
            ),
            FundMovement(
                fund_id=fund.id,
                account_id=payload.destination_account_id,
                event_id=event.id,
                operation_id=None,
                amount=payload.amount,
            ),
        ],
    )
    session.flush()
    validate_account_coverage(session, physical_balances)
    return event


def create_fund_transfer(session: Session, payload: FundTransferCreateRequest) -> FundEvent:
    funds = _lock_fund_references(session, {payload.source_fund_id, payload.destination_fund_id})
    if any(fund.archived_at is not None for fund in funds.values()):
        raise FundNotFoundError
    if fund_balance(session, payload.source_fund_id, payload.account_id) < payload.amount:
        raise FundBalanceError
    event = _event(session, FundEventType.FUND_TRANSFER, payload.occurred_on, payload.description)
    _add_fund_movements(
        session,
        [
            FundMovement(
                fund_id=payload.source_fund_id,
                account_id=payload.account_id,
                event_id=event.id,
                operation_id=None,
                amount=-payload.amount,
            ),
            FundMovement(
                fund_id=payload.destination_fund_id,
                account_id=payload.account_id,
                event_id=event.id,
                operation_id=None,
                amount=payload.amount,
            ),
        ],
    )
    session.flush()
    return event


def _event(
    session: Session,
    event_type: FundEventType,
    occurred_on: date,
    description: str | None,
    *,
    caused_by_operation_id: UUID | None = None,
) -> FundEvent:
    now = datetime.now(UTC)
    event = FundEvent(
        type=event_type,
        occurred_on=occurred_on,
        description=description,
        caused_by_operation_id=caused_by_operation_id,
        created_at=now,
    )
    session.add(event)
    session.flush()
    return event


def _add_fund_movements(session: Session, movements: list[FundMovement]) -> None:
    session.add_all(movements)


def _lock_fund_references(session: Session, fund_ids: set[UUID]) -> dict[UUID, Fund]:
    if not fund_ids:
        return {}
    funds = session.scalars(
        select(Fund).where(Fund.id.in_(fund_ids)).order_by(Fund.id).with_for_update()
    ).all()
    if len(funds) != len(fund_ids):
        raise FundNotFoundError
    return {fund.id: fund for fund in funds}


def replace_operation_movements(
    session: Session,
    operation_id: UUID,
    movements: dict[tuple[UUID, UUID], Decimal],
    *,
    allow_archived_fund_ids: set[UUID],
) -> None:
    fund_ids = {fund_id for fund_id, _ in movements} | allow_archived_fund_ids
    funds = _lock_fund_references(session, fund_ids)
    if any(
        fund.archived_at is not None and fund.id not in allow_archived_fund_ids
        for fund in funds.values()
    ):
        raise FundNotFoundError
    session.execute(delete(FundMovement).where(FundMovement.operation_id == operation_id))
    _add_fund_movements(
        session,
        [
            FundMovement(
                fund_id=fund_id,
                account_id=account_id,
                operation_id=operation_id,
                event_id=None,
                amount=amount,
            )
            for (fund_id, account_id), amount in movements.items()
        ],
    )
    session.flush()
    if any(
        fund.archived_at is not None and fund_balance(session, fund.id) != 0
        for fund in funds.values()
    ):
        raise FundArchivedMutationError


def operation_fund_movements(
    session: Session, operation_id: UUID
) -> dict[tuple[UUID, UUID], Decimal]:
    return {
        (fund_id, account_id): Decimal(amount)
        for fund_id, account_id, amount in session.execute(
            select(FundMovement.fund_id, FundMovement.account_id, FundMovement.amount).where(
                FundMovement.operation_id == operation_id
            )
        )
    }


def fund_names(session: Session, fund_ids: set[UUID]) -> dict[UUID, str]:
    return {
        fund.id: fund.name
        for fund in session.scalars(select(Fund).where(Fund.id.in_(fund_ids))).all()
    }


def event_response(session: Session, event: FundEvent) -> FundEventResponse:
    rows = session.execute(
        select(FundMovement.fund_id, FundMovement.account_id, FundMovement.amount)
        .where(FundMovement.event_id == event.id)
        .order_by(FundMovement.amount, FundMovement.id)
    ).all()
    fund_names = {
        fund.id: fund.name
        for fund in session.scalars(select(Fund).where(Fund.id.in_({row[0] for row in rows}))).all()
    }
    names = account_names(session, {row[1] for row in rows})
    reserve_rows = session.execute(
        select(FundReserveMovement.account_id, FundReserveMovement.amount)
        .where(FundReserveMovement.event_id == event.id)
        .order_by(FundReserveMovement.account_id)
    ).all()
    reserve_names = account_names(session, {row[0] for row in reserve_rows})
    return FundEventResponse(
        id=event.id,
        type=event.type,
        caused_by_operation_id=event.caused_by_operation_id,
        occurred_on=event.occurred_on,
        description=event.description,
        movements=[
            FundMovementResponse(
                fund_id=fund_id,
                fund_name=fund_names[fund_id],
                account_id=account_id,
                account_name=names[account_id],
                amount=format(amount, "f"),
            )
            for fund_id, account_id, amount in rows
        ],
        reserve_movements=[
            FundReserveMovementResponse(
                account_id=account_id,
                account_name=reserve_names[account_id],
                amount=format(amount, "f"),
            )
            for account_id, amount in reserve_rows
        ],
        created_at=event.created_at,
    )


def history_source_ids(
    session: Session, *, fund_id: UUID | None, account_id: UUID | None
) -> tuple[set[UUID], set[UUID]]:
    conditions = []
    if fund_id is not None:
        conditions.append(FundMovement.fund_id == fund_id)
    if account_id is not None:
        conditions.append(FundMovement.account_id == account_id)
    sources = session.execute(
        select(FundMovement.event_id, FundMovement.operation_id).where(*conditions)
    ).all()
    event_ids = {event_id for event_id, _ in sources if event_id is not None}
    if fund_id is None:
        reserve_conditions = []
        if account_id is not None:
            reserve_conditions.append(FundReserveMovement.account_id == account_id)
        event_ids.update(
            event_id
            for (event_id,) in session.execute(
                select(FundReserveMovement.event_id).where(*reserve_conditions)
            )
        )
    operation_ids = {operation_id for _, operation_id in sources if operation_id is not None}
    return event_ids, operation_ids


def event_responses(session: Session, event_ids: set[UUID]) -> list[FundEventResponse]:
    events = session.scalars(select(FundEvent).where(FundEvent.id.in_(event_ids))).all()
    return [event_response(session, event) for event in events]


def existing_fund_release(session: Session, request_id: UUID) -> FundEventResponse | None:
    event = session.get(FundEvent, request_id)
    if event is None:
        return None
    if event.type != FundEventType.FUND_RELEASE:
        raise FundConflictError
    return event_response(session, event)


def create_fund_release(session: Session, payload: FundReleaseRequest) -> UUID:
    """Release a position; the caller owns account locks and the transaction."""
    _lock_definitions(session)
    fund = _lock_fund_references(session, {payload.fund_id})[payload.fund_id]
    if fund.archived_at is not None:
        raise FundNotFoundError
    if fund_balance(session, fund.id, payload.account_id) < payload.amount:
        raise FundBalanceError
    event = FundEvent(
        id=payload.request_id,
        type=FundEventType.FUND_RELEASE,
        occurred_on=payload.occurred_on,
        description=payload.description,
        created_at=datetime.now(UTC),
    )
    session.add(event)
    session.flush()
    session.add(
        FundMovement(
            fund_id=fund.id,
            account_id=payload.account_id,
            event_id=event.id,
            amount=-payload.amount,
        )
    )
    session.flush()
    return event.id


def link_fund_release(session: Session, event_id: UUID, operation_id: UUID) -> None:
    event = session.get(FundEvent, event_id)
    assert event is not None and event.type == FundEventType.FUND_RELEASE
    event.caused_by_operation_id = operation_id
    session.flush()


def operation_has_fund_release(session: Session, operation_id: UUID) -> bool:
    return (
        session.scalar(
            select(FundEvent.id).where(
                FundEvent.caused_by_operation_id == operation_id,
                FundEvent.type == FundEventType.FUND_RELEASE,
            )
        )
        is not None
    )
