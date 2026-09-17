from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.modules.accounts.contracts import (
    account_names,
    list_account_identities,
    lock_account_references,
)
from app.modules.categories.contracts import (
    CategoryType,
    category_name,
    category_root_map,
    category_subtree_ids,
    validate_category_reference,
)
from app.modules.funds.contracts import (
    LegacyTransferAllocationMatch,
    fund_names,
    lock_operation_dependent_allocation,
    operation_fund_movements,
    operation_has_fund_release,
    operation_has_managed_reservation,
    rebalance_reserve,
    remove_operation_dependent_events,
    remove_operation_reserve_distributions,
    replace_operation_movements,
    validate_account_coverage,
)
from app.modules.operations.ledger import account_balance
from app.modules.operations.models import AccountMovement, FinancialOperation, OperationType
from app.modules.operations.schemas import (
    CategoryAmountResponse,
    CategorySummaryResponse,
    MovementResponse,
    OperationCreateRequest,
    OperationFundMovementResponse,
    OperationPageResponse,
    OperationResponse,
)
from app.modules.settings.contracts import application_timezone


class OperationNotFoundError(RuntimeError):
    pass


class OperationConflictError(RuntimeError):
    pass


class InsufficientBalanceError(RuntimeError):
    pass


class OperationLinkedError(RuntimeError):
    pass


class OperationAllocationLinkedError(RuntimeError):
    pass


class OperationDepreciationLinkedError(RuntimeError):
    pass


class OperationFundReleaseLinkedError(RuntimeError):
    pass


class FutureOperationDateError(RuntimeError):
    pass


LINKED_OCCURRENCE_CONSTRAINT = "fk_expected_occurrences_actual_operation"


@dataclass(frozen=True, slots=True)
class OperationDraft:
    type: OperationType
    occurred_on: date
    amount: Decimal
    description: str | None
    reason: str | None
    account_id: UUID
    destination_account_id: UUID | None
    category_id: UUID | None
    fund_id: UUID | None
    fund_amount: Decimal | None


def _draft(payload: OperationCreateRequest) -> OperationDraft:
    return OperationDraft(**payload.model_dump(exclude={"version"}))


def reject_future_operation_date(session: Session, occurred_on: date) -> None:
    """Keep the public Operations journal factual in the Hermes calendar."""
    today = datetime.now(UTC).astimezone(ZoneInfo(application_timezone(session))).date()
    if occurred_on > today:
        raise FutureOperationDateError


def _movement_amounts(draft: OperationDraft) -> dict[UUID, Decimal]:
    if draft.type == OperationType.INCOME:
        return {draft.account_id: draft.amount}
    if draft.type == OperationType.EXPENSE:
        return {draft.account_id: -draft.amount}
    if draft.type == OperationType.TRANSFER:
        assert draft.destination_account_id is not None
        return {draft.account_id: -draft.amount, draft.destination_account_id: draft.amount}
    return {draft.account_id: draft.amount}


def _fund_movement_amounts(draft: OperationDraft) -> dict[tuple[UUID, UUID], Decimal]:
    if draft.fund_id is None:
        return {}
    if draft.type == OperationType.EXPENSE:
        return {(draft.fund_id, draft.account_id): -draft.amount}
    assert draft.type == OperationType.TRANSFER
    assert draft.destination_account_id is not None
    assert draft.fund_amount is not None
    return {
        (draft.fund_id, draft.account_id): -draft.fund_amount,
        (draft.fund_id, draft.destination_account_id): draft.fund_amount,
    }


def _validate_category(
    session: Session, draft: OperationDraft, old_category_id: UUID | None
) -> None:
    if draft.category_id is None:
        return
    expected = CategoryType.INCOME if draft.type == OperationType.INCOME else CategoryType.EXPENSE
    validate_category_reference(
        session,
        draft.category_id,
        expected_type=expected,
        allow_archived=draft.category_id == old_category_id,
    )


def _lock_and_check_balances(
    session: Session,
    *,
    old_amounts: dict[UUID, Decimal],
    new_amounts: dict[UUID, Decimal],
    extra_account_ids: set[UUID] | None = None,
) -> None:
    account_ids = set(old_amounts) | set(new_amounts) | (extra_account_ids or set())
    lock_account_references(
        session,
        account_ids,
        allow_archived_ids=set(old_amounts),
    )
    for account_id in account_ids:
        prospective = (
            account_balance(session, account_id)
            - old_amounts.get(account_id, Decimal(0))
            + new_amounts.get(account_id, Decimal(0))
        )
        if prospective < 0:
            raise InsufficientBalanceError


def _add_movements(session: Session, operation_id: UUID, amounts: dict[UUID, Decimal]) -> None:
    session.add_all(
        AccountMovement(operation_id=operation_id, account_id=account_id, amount=amount)
        for account_id, amount in amounts.items()
    )


def create_operation(session: Session, payload: OperationCreateRequest) -> FinancialOperation:
    draft = _draft(payload)
    _validate_category(session, draft, None)
    amounts = _movement_amounts(draft)
    fund_amounts = _fund_movement_amounts(draft)
    extra_ids = {item.id for item in list_account_identities(session)} if fund_amounts else set()
    _lock_and_check_balances(
        session, old_amounts={}, new_amounts=amounts, extra_account_ids=extra_ids
    )
    now = datetime.now(UTC)
    operation = FinancialOperation(
        type=draft.type,
        occurred_on=draft.occurred_on,
        description=draft.description,
        reason=draft.reason,
        category_id=draft.category_id,
        created_at=now,
        updated_at=now,
        version=1,
    )
    session.add(operation)
    session.flush()
    _add_movements(session, operation.id, amounts)
    session.flush()
    replace_operation_movements(
        session,
        operation.id,
        fund_amounts,
        allow_archived_fund_ids=set(),
    )
    if fund_amounts:
        rebalance_reserve(
            session,
            occurred_on=operation.occurred_on,
            caused_by_operation_id=operation.id,
        )
    validate_account_coverage(
        session, {account_id: account_balance(session, account_id) for account_id in amounts}
    )
    return operation


def _get_operation(session: Session, operation_id: UUID, *, lock: bool) -> FinancialOperation:
    query = select(FinancialOperation).where(FinancialOperation.id == operation_id)
    if lock:
        query = query.with_for_update()
    operation = session.scalar(query)
    if operation is None:
        raise OperationNotFoundError
    return operation


def _amounts_for_operation(session: Session, operation_id: UUID) -> dict[UUID, Decimal]:
    return {
        account_id: Decimal(amount)
        for account_id, amount in session.execute(
            select(AccountMovement.account_id, AccountMovement.amount).where(
                AccountMovement.operation_id == operation_id
            )
        )
    }


def _legacy_transfer_allocation_match(
    operation: FinancialOperation, amounts: dict[UUID, Decimal]
) -> LegacyTransferAllocationMatch | None:
    if operation.type != OperationType.TRANSFER:
        return None
    destination_account_id, amount = next(
        (account_id, amount) for account_id, amount in amounts.items() if amount > 0
    )
    return LegacyTransferAllocationMatch(
        occurred_on=operation.occurred_on,
        description=operation.description,
        operation_created_at=operation.created_at,
        destination_account_id=destination_account_id,
        amount=amount,
    )


def update_operation(
    session: Session,
    operation_id: UUID,
    payload: OperationCreateRequest,
    *,
    expected_version: int,
) -> FinancialOperation:
    operation = _get_operation(session, operation_id, lock=True)
    if operation.version != expected_version:
        raise OperationConflictError
    old_amounts = _amounts_for_operation(session, operation.id)
    legacy_transfer_allocation = _legacy_transfer_allocation_match(operation, old_amounts)
    old_fund_amounts = operation_fund_movements(session, operation.id)
    has_release = operation_has_fund_release(
        session, operation.id
    ) or operation_has_managed_reservation(session, operation.id)
    draft = _draft(payload)
    _validate_category(session, draft, operation.category_id)
    new_amounts = _movement_amounts(draft)
    new_fund_amounts = _fund_movement_amounts(draft)
    extra_ids = (
        {item.id for item in list_account_identities(session)}
        if old_fund_amounts or new_fund_amounts or has_release
        else set()
    )
    _lock_and_check_balances(
        session,
        old_amounts=old_amounts,
        new_amounts=new_amounts,
        extra_account_ids=extra_ids,
    )
    if operation_has_managed_reservation(session, operation.id):
        raise OperationDepreciationLinkedError
    if has_release:
        raise OperationFundReleaseLinkedError
    if lock_operation_dependent_allocation(
        session,
        operation.id,
        legacy_transfer_allocation=legacy_transfer_allocation,
    ):
        raise OperationAllocationLinkedError
    remove_operation_reserve_distributions(session, operation.id)
    session.execute(delete(AccountMovement).where(AccountMovement.operation_id == operation.id))
    operation.type = draft.type
    operation.occurred_on = draft.occurred_on
    operation.description = draft.description
    operation.reason = draft.reason
    operation.category_id = draft.category_id
    operation.updated_at = datetime.now(UTC)
    operation.version += 1
    _add_movements(session, operation.id, new_amounts)
    session.flush()
    replace_operation_movements(
        session,
        operation.id,
        new_fund_amounts,
        allow_archived_fund_ids={fund_id for fund_id, _ in old_fund_amounts},
    )
    if old_fund_amounts or new_fund_amounts:
        rebalance_reserve(
            session,
            occurred_on=operation.occurred_on,
            caused_by_operation_id=operation.id,
        )
    affected_ids = set(old_amounts) | set(new_amounts)
    validate_account_coverage(
        session, {account_id: account_balance(session, account_id) for account_id in affected_ids}
    )
    return operation


def delete_operation(session: Session, operation_id: UUID, *, expected_version: int) -> None:
    operation = _get_operation(session, operation_id, lock=True)
    if operation_has_managed_reservation(session, operation.id):
        raise OperationDepreciationLinkedError
    if operation.version != expected_version:
        raise OperationConflictError
    old_amounts = _amounts_for_operation(session, operation.id)
    old_fund_amounts = operation_fund_movements(session, operation.id)
    has_release = operation_has_fund_release(
        session, operation.id
    ) or operation_has_managed_reservation(session, operation.id)
    extra_ids = (
        {item.id for item in list_account_identities(session)}
        if old_fund_amounts or has_release
        else set()
    )
    _lock_and_check_balances(
        session,
        old_amounts=old_amounts,
        new_amounts={},
        extra_account_ids=extra_ids,
    )
    legacy_transfer_allocation = (
        None if has_release else _legacy_transfer_allocation_match(operation, old_amounts)
    )
    remove_operation_dependent_events(
        session,
        operation.id,
        legacy_transfer_allocation=legacy_transfer_allocation,
    )
    replace_operation_movements(
        session,
        operation.id,
        {},
        allow_archived_fund_ids={fund_id for fund_id, _ in old_fund_amounts},
    )
    session.delete(operation)
    try:
        session.flush()
    except IntegrityError as error:
        diagnostic = getattr(error.orig, "diag", None)
        if getattr(diagnostic, "constraint_name", None) != LINKED_OCCURRENCE_CONSTRAINT:
            raise
        raise OperationLinkedError from error
    validate_account_coverage(
        session,
        {
            account_id: account_balance(session, account_id)
            for account_id in set(old_amounts) | extra_ids
        },
    )


def _response(session: Session, operation: FinancialOperation) -> OperationResponse:
    rows = session.execute(
        select(AccountMovement.account_id, AccountMovement.amount)
        .where(AccountMovement.operation_id == operation.id)
        .order_by(AccountMovement.amount, AccountMovement.account_id)
    ).all()
    names = account_names(session, {account_id for account_id, _ in rows})
    movements = [
        MovementResponse(
            account_id=account_id, account_name=names[account_id], amount=format(amount, "f")
        )
        for account_id, amount in rows
    ]
    negative = next((item for item in movements if Decimal(item.amount) < 0), movements[0])
    positive = next((item for item in movements if Decimal(item.amount) > 0), None)
    if operation.type == OperationType.BALANCE_ADJUSTMENT:
        amount = movements[0].amount
    else:
        amount = format(abs(Decimal(negative.amount)), "f")
    resolved_category_name = (
        category_name(session, operation.category_id) if operation.category_id is not None else None
    )
    raw_fund_rows = operation_fund_movements(session, operation.id)
    names_by_fund = fund_names(session, {fund_id for fund_id, _ in raw_fund_rows})
    fund_rows = [
        OperationFundMovementResponse(
            fund_id=movement_fund_id,
            fund_name=names_by_fund[movement_fund_id],
            account_id=account_id,
            account_name=names[account_id],
            amount=format(amount, "f"),
        )
        for (movement_fund_id, account_id), amount in sorted(
            raw_fund_rows.items(), key=lambda item: (item[1], item[0][1])
        )
    ]
    fund_id = fund_rows[0].fund_id if fund_rows else None
    fund_amount: str | None = None
    if fund_rows:
        negative_fund = next((item for item in fund_rows if Decimal(item.amount) < 0), fund_rows[0])
        fund_amount = format(abs(Decimal(negative_fund.amount)), "f")
    return OperationResponse(
        id=operation.id,
        type=operation.type,
        occurred_on=operation.occurred_on,
        amount=amount,
        description=operation.description,
        reason=operation.reason,
        category_id=operation.category_id,
        category_name=resolved_category_name,
        account_id=negative.account_id,
        destination_account_id=(positive.account_id if len(movements) == 2 and positive else None),
        movements=movements,
        fund_id=fund_id,
        fund_amount=fund_amount,
        fund_movements=fund_rows,
        version=operation.version,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
    )


def get_operation_response(session: Session, operation_id: UUID) -> OperationResponse:
    return _response(session, _get_operation(session, operation_id, lock=False))


def list_operation_responses(
    session: Session,
    *,
    page: int,
    page_size: int,
    occurred_from: date | None,
    occurred_to: date | None,
    account_id: UUID | None,
    operation_type: OperationType | None,
    category_id: UUID | None,
) -> OperationPageResponse:
    conditions: list[ColumnElement[bool]] = []
    if occurred_from is not None:
        conditions.append(FinancialOperation.occurred_on >= occurred_from)
    if occurred_to is not None:
        conditions.append(FinancialOperation.occurred_on <= occurred_to)
    if operation_type is not None:
        conditions.append(FinancialOperation.type == operation_type)
    if category_id is not None:
        conditions.append(
            FinancialOperation.category_id.in_(category_subtree_ids(session, category_id))
        )
    if account_id is not None:
        conditions.append(
            FinancialOperation.id.in_(
                select(AccountMovement.operation_id).where(AccountMovement.account_id == account_id)
            )
        )
    filtered_operation_ids = select(FinancialOperation.id).where(*conditions)
    total = session.scalar(select(func.count()).select_from(FinancialOperation).where(*conditions))
    movement_total_conditions: list[ColumnElement[bool]] = [
        AccountMovement.operation_id.in_(filtered_operation_ids)
    ]
    if account_id is not None:
        movement_total_conditions.append(AccountMovement.account_id == account_id)
    total_amount = session.scalar(
        select(func.coalesce(func.sum(AccountMovement.amount), 0)).where(*movement_total_conditions)
    )
    operations = session.scalars(
        select(FinancialOperation)
        .where(*conditions)
        .order_by(
            FinancialOperation.occurred_on.desc(),
            FinancialOperation.created_at.desc(),
            FinancialOperation.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return OperationPageResponse(
        items=[_response(session, operation) for operation in operations],
        page=page,
        page_size=page_size,
        total=int(total or 0),
        total_amount=format(Decimal(total_amount or 0), "f"),
    )


def category_summary(
    session: Session, *, from_on: date, through_on: date
) -> CategorySummaryResponse:
    roots = category_root_map(session)
    roots_by_id = {root.id: root for root in roots.values()}
    totals: dict[tuple[CategoryType, UUID], Decimal] = {}
    rows = session.execute(
        select(
            FinancialOperation.category_id,
            FinancialOperation.type,
            func.sum(AccountMovement.amount),
        )
        .join(AccountMovement, AccountMovement.operation_id == FinancialOperation.id)
        .where(
            FinancialOperation.occurred_on.between(from_on, through_on),
            FinancialOperation.type.in_([OperationType.INCOME, OperationType.EXPENSE]),
        )
        .group_by(FinancialOperation.category_id, FinancialOperation.type)
    )
    for category_id, operation_type, raw_amount in rows:
        if category_id is None or category_id not in roots:
            continue
        root = roots[category_id]
        category_type = (
            CategoryType.INCOME if operation_type == OperationType.INCOME else CategoryType.EXPENSE
        )
        key = (category_type, root.id)
        totals[key] = totals.get(key, Decimal(0)) + abs(Decimal(raw_amount))

    def response(category_type: CategoryType) -> list[CategoryAmountResponse]:
        items = [
            CategoryAmountResponse(
                category_id=root_id,
                category_name=roots_by_id[root_id].name,
                amount=format(amount, "f"),
            )
            for (item_type, root_id), amount in totals.items()
            if item_type == category_type
        ]
        return sorted(items, key=lambda item: (-Decimal(item.amount), item.category_name))

    return CategorySummaryResponse(
        from_on=from_on,
        through_on=through_on,
        income=response(CategoryType.INCOME),
        expense=response(CategoryType.EXPENSE),
    )
