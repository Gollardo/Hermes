from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.accounts.contracts import (
    account_names,
    list_account_identities,
    lock_account_references,
)
from app.modules.funds.contracts import (
    AllocationCreateRequest,
    AllocationItem,
    AllocationPreviewResponse,
    FundConflictError,
    FundCreateRequest,
    FundEventResponse,
    FundHistoryResponse,
    FundMovementResponse,
    FundReleaseRequest,
    FundReleaseResponse,
    FundReserveReleaseRequest,
    FundResponse,
    FundSummaryResponse,
    FundTransferCreateRequest,
    FundUpdateRequest,
    RedistributionCreateRequest,
    allocation_preview_with_free_balance,
    archive_fund,
    create_allocation_with_free_balance,
    create_fund_definition,
    create_fund_release,
    create_fund_transfer,
    create_redistribution_with_physical_balances,
    event_response,
    event_responses,
    existing_fund_release,
    fund_names,
    fund_response,
    history_source_ids,
    link_fund_release,
    operation_fund_movements,
    rebalance_reserve,
    release_reserve,
    reserved_balance,
    summary_with_physical_balances,
    update_fund,
    validate_account_coverage,
)
from app.modules.operations.contracts import (
    PhysicalTransferDraft,
    account_balance,
    get_operation_response,
    operation_history_references,
    post_physical_transfer,
    reject_future_operation_date,
)


def _lock_all_accounts(session: Session) -> None:
    account_ids = {account.id for account in list_account_identities(session)}
    lock_account_references(session, account_ids, allow_archived_ids=account_ids)


def fund_summary(session: Session) -> FundSummaryResponse:
    account_ids = {account.id for account in list_account_identities(session)}
    physical = {account_id: account_balance(session, account_id) for account_id in account_ids}
    return summary_with_physical_balances(session, physical)


def create_fund_with_initial_allocation(
    session: Session, payload: FundCreateRequest
) -> FundResponse:
    """Create one fund and optionally reserve free money only for that fund atomically."""
    _lock_all_accounts(session)
    initial_free: Decimal | None = None
    if payload.initial_account_id is not None:
        initial_free = account_balance(session, payload.initial_account_id) - reserved_balance(
            session, payload.initial_account_id
        )

    fund_id = create_fund_definition(
        session,
        name=payload.name,
        description=payload.description,
        percentage=payload.allocation_percentage,
        target_amount=payload.target_amount,
    )
    if (
        payload.initial_account_id is not None
        and payload.initial_amount is not None
        and payload.initial_occurred_on is not None
    ):
        assert initial_free is not None
        create_allocation_with_free_balance(
            session,
            AllocationCreateRequest(
                account_id=payload.initial_account_id,
                amount=payload.initial_amount,
                occurred_on=payload.initial_occurred_on,
                description=None,
                allocations=[AllocationItem(fund_id=fund_id, amount=payload.initial_amount)],
            ),
            initial_free,
        )
    rebalance_reserve(session, occurred_on=payload.initial_occurred_on)
    return fund_response(session, fund_id)


def preview_allocation(
    session: Session, account_id: UUID, amount: Decimal
) -> AllocationPreviewResponse:
    lock_account_references(session, {account_id})
    free = account_balance(session, account_id) - reserved_balance(session, account_id)
    return allocation_preview_with_free_balance(session, account_id, amount, free)


def allocate_funds(session: Session, payload: AllocationCreateRequest) -> FundEventResponse:
    lock_account_references(session, {payload.account_id})
    free = account_balance(session, payload.account_id) - reserved_balance(
        session, payload.account_id
    )
    event = create_allocation_with_free_balance(session, payload, free)
    return event_response(session, event)


def redistribute_fund(session: Session, payload: RedistributionCreateRequest) -> FundEventResponse:
    account_ids = {payload.source_account_id, payload.destination_account_id}
    lock_account_references(session, account_ids)
    physical = {account_id: account_balance(session, account_id) for account_id in account_ids}
    event = create_redistribution_with_physical_balances(session, payload, physical)
    return event_response(session, event)


def transfer_between_funds(
    session: Session, payload: FundTransferCreateRequest
) -> FundEventResponse:
    _lock_all_accounts(session)
    event = create_fund_transfer(session, payload)
    rebalance_reserve(session, occurred_on=payload.occurred_on)
    return event_response(session, event)


def replace_fund_definition(
    session: Session, fund_id: UUID, payload: FundUpdateRequest
) -> FundResponse:
    _lock_all_accounts(session)
    fund = update_fund(session, fund_id, payload)
    rebalance_reserve(session)
    return fund_response(session, fund.id)


def change_fund_lifecycle(
    session: Session, fund_id: UUID, *, restore: bool, expected_version: int
) -> FundResponse:
    if restore:
        _lock_all_accounts(session)
    fund = archive_fund(session, fund_id, restore=restore, expected_version=expected_version)
    if restore:
        rebalance_reserve(session)
    return fund_response(session, fund.id)


def release_fund_reserve(session: Session, payload: FundReserveReleaseRequest) -> FundEventResponse:
    lock_account_references(session, {payload.account_id}, allow_archived_ids={payload.account_id})
    return event_response(session, release_reserve(session, payload))


def fund_history(
    session: Session,
    *,
    page: int,
    page_size: int,
    fund_id: UUID | None,
    account_id: UUID | None,
) -> FundHistoryResponse:
    event_ids, operation_ids = history_source_ids(session, fund_id=fund_id, account_id=account_id)
    items = event_responses(session, event_ids)
    references = operation_history_references(session, operation_ids)
    raw_by_operation = {
        operation_id: operation_fund_movements(session, operation_id)
        for operation_id in operation_ids
    }
    account_ids = {
        movement_account_id
        for raw_movements in raw_by_operation.values()
        for _, movement_account_id in raw_movements
    }
    names = account_names(session, account_ids) if account_ids else {}
    for operation_id, reference in references.items():
        raw_movements = raw_by_operation[operation_id]
        names_by_fund = fund_names(
            session, {movement_fund_id for movement_fund_id, _ in raw_movements}
        )
        items.append(
            FundEventResponse(
                id=reference.id,
                type=reference.type.value,
                occurred_on=reference.occurred_on,
                description=reference.description,
                movements=[
                    FundMovementResponse(
                        fund_id=movement_fund_id,
                        fund_name=names_by_fund[movement_fund_id],
                        account_id=movement_account_id,
                        account_name=names[movement_account_id],
                        amount=format(amount, "f"),
                    )
                    for (movement_fund_id, movement_account_id), amount in raw_movements.items()
                ],
                created_at=reference.created_at,
            )
        )
    items.sort(key=lambda item: (item.occurred_on, item.created_at, item.id), reverse=True)
    total = len(items)
    offset = (page - 1) * page_size
    return FundHistoryResponse(
        items=items[offset : offset + page_size],
        page=page,
        page_size=page_size,
        total=total,
    )


def release_fund(session: Session, payload: FundReleaseRequest) -> FundReleaseResponse:
    """Release once, optionally transfer, then refill from reserve atomically."""
    _lock_all_accounts(session)
    existing = existing_fund_release(session, payload.request_id)
    if existing is not None:
        destination = None
        if existing.caused_by_operation_id is not None:
            destination = get_operation_response(
                session, existing.caused_by_operation_id
            ).destination_account_id
        if (
            existing.occurred_on != payload.occurred_on
            or existing.description != payload.description
            or destination != payload.destination_account_id
            or len(existing.movements) != 1
            or existing.movements[0].fund_id != payload.fund_id
            or existing.movements[0].account_id != payload.account_id
            or Decimal(existing.movements[0].amount) != -payload.amount
        ):
            raise FundConflictError
        return FundReleaseResponse(operation_id=existing.caused_by_operation_id, release=existing)
    account_ids = {payload.account_id}
    if payload.destination_account_id is not None:
        account_ids.add(payload.destination_account_id)
    lock_account_references(session, account_ids)
    reject_future_operation_date(session, payload.occurred_on)
    event_id = create_fund_release(session, payload)
    operation_id = None
    if payload.destination_account_id is not None:
        operation_id = post_physical_transfer(
            session,
            PhysicalTransferDraft(
                occurred_on=payload.occurred_on,
                amount=payload.amount,
                description=payload.description,
                source_account_id=payload.account_id,
                destination_account_id=payload.destination_account_id,
            ),
        )
        link_fund_release(session, event_id, operation_id)
    rebalance_reserve(session, occurred_on=payload.occurred_on, caused_by_operation_id=operation_id)
    validate_account_coverage(
        session,
        {
            account.id: account_balance(session, account.id)
            for account in list_account_identities(session)
        },
    )
    release = existing_fund_release(session, event_id)
    assert release is not None
    return FundReleaseResponse(operation_id=operation_id, release=release)
