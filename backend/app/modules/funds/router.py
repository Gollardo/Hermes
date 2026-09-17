from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.application.funds import (
    allocate_funds,
    change_fund_lifecycle,
    create_fund_with_initial_allocation,
    fund_history,
    fund_summary,
    preview_allocation,
    redistribute_fund,
    release_fund,
    release_fund_reserve,
    replace_fund_definition,
    transfer_between_funds,
)
from app.application.transfer_allocation import transfer_and_allocate
from app.core.database import DatabaseSession
from app.modules.accounts.contracts import AccountReferenceError
from app.modules.funds.schemas import (
    AllocationCreateRequest,
    AllocationPreviewRequest,
    AllocationPreviewResponse,
    FundCreateRequest,
    FundEventResponse,
    FundHistoryResponse,
    FundLifecycleRequest,
    FundReleaseRequest,
    FundReleaseResponse,
    FundReserveReleaseRequest,
    FundResponse,
    FundSummaryResponse,
    FundTransferCreateRequest,
    FundUpdateRequest,
    RedistributionCreateRequest,
    TransferAllocationCreateRequest,
    TransferAllocationResponse,
)
from app.modules.funds.service import (
    DynamicFundTargetsRequiredError,
    FundAllocationUnavailableError,
    FundArchiveBalanceError,
    FundBalanceError,
    FundConflictError,
    FundCoverageError,
    FundNotFoundError,
    FundPercentageLimitError,
    FundReserveBalanceError,
    FundTargetCapacityError,
    list_funds,
)
from app.modules.operations.contracts import FutureOperationDateError, InsufficientBalanceError

read_router = APIRouter(prefix="/funds", tags=["funds"])
write_router = APIRouter(prefix="/funds", tags=["funds"])


def _raise_domain_error(error: RuntimeError) -> None:
    mapping: list[tuple[type[RuntimeError], int, str, str]] = [
        (
            FutureOperationDateError,
            409,
            "future_operation_requires_plan",
            "A release cannot be future-dated",
        ),
        (
            DynamicFundTargetsRequiredError,
            409,
            "dynamic_fund_targets_required",
            "Every non-archived fund needs a target in dynamic mode",
        ),
        (FundNotFoundError, 404, "fund_not_found", "Fund is unavailable"),
        (
            FundAllocationUnavailableError,
            409,
            "fund_allocation_unavailable",
            "No active fund percentage is configured",
        ),
        (FundConflictError, 409, "fund_conflict", "Fund was changed"),
        (FundPercentageLimitError, 409, "fund_percentage_limit", "Active percentages exceed 100"),
        (
            FundArchiveBalanceError,
            409,
            "fund_has_balance",
            "Fund must have zero balance before archive",
        ),
        (FundBalanceError, 409, "insufficient_fund_balance", "Insufficient fund balance"),
        (FundReserveBalanceError, 409, "insufficient_fund_reserve", "Insufficient fund reserve"),
        (FundTargetCapacityError, 409, "fund_target_capacity", "Fund allocation exceeds target"),
        (
            FundCoverageError,
            409,
            "insufficient_free_balance",
            "Fund reservations exceed physical balance",
        ),
        (AccountReferenceError, 409, "invalid_account_reference", "Account is unavailable"),
        (InsufficientBalanceError, 409, "insufficient_balance", "Insufficient balance"),
    ]
    for error_type, status_code, code, message in mapping:
        if isinstance(error, error_type):
            raise HTTPException(status_code, detail={"code": code, "message": message})
    raise error


@read_router.get("", response_model=list[FundResponse])
def read_funds(session: DatabaseSession, include_archived: bool = True) -> list[FundResponse]:
    return list_funds(session, include_archived=include_archived)


@read_router.get("/summary", response_model=FundSummaryResponse)
def read_summary(session: DatabaseSession) -> FundSummaryResponse:
    return fund_summary(session)


@read_router.get("/history", response_model=FundHistoryResponse)
def read_history(
    session: DatabaseSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    fund_id: UUID | None = None,
    account_id: UUID | None = None,
) -> FundHistoryResponse:
    return fund_history(
        session, page=page, page_size=page_size, fund_id=fund_id, account_id=account_id
    )


@write_router.post("", response_model=FundResponse, status_code=status.HTTP_201_CREATED)
def add_fund(payload: FundCreateRequest, session: DatabaseSession) -> FundResponse:
    try:
        return create_fund_with_initial_allocation(session, payload)
    except (
        AccountReferenceError,
        FundBalanceError,
        FundCoverageError,
        FundNotFoundError,
        FundPercentageLimitError,
        DynamicFundTargetsRequiredError,
        FundTargetCapacityError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.put("/{fund_id}", response_model=FundResponse)
def replace_fund(
    fund_id: UUID, payload: FundUpdateRequest, session: DatabaseSession
) -> FundResponse:
    try:
        return replace_fund_definition(session, fund_id, payload)
    except (
        AccountReferenceError,
        FundNotFoundError,
        FundConflictError,
        FundPercentageLimitError,
        DynamicFundTargetsRequiredError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post("/{fund_id}/archive", response_model=FundResponse)
def archive(fund_id: UUID, payload: FundLifecycleRequest, session: DatabaseSession) -> FundResponse:
    try:
        return change_fund_lifecycle(
            session, fund_id, restore=False, expected_version=payload.version
        )
    except (FundNotFoundError, FundConflictError, FundArchiveBalanceError) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post("/{fund_id}/restore", response_model=FundResponse)
def restore(fund_id: UUID, payload: FundLifecycleRequest, session: DatabaseSession) -> FundResponse:
    try:
        return change_fund_lifecycle(
            session, fund_id, restore=True, expected_version=payload.version
        )
    except (
        AccountReferenceError,
        FundNotFoundError,
        FundConflictError,
        FundPercentageLimitError,
        DynamicFundTargetsRequiredError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post("/allocation-preview", response_model=AllocationPreviewResponse)
def preview(
    payload: AllocationPreviewRequest, session: DatabaseSession
) -> AllocationPreviewResponse:
    try:
        return preview_allocation(session, payload.account_id, payload.amount)
    except AccountReferenceError as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post(
    "/allocations", response_model=FundEventResponse, status_code=status.HTTP_201_CREATED
)
def allocate(payload: AllocationCreateRequest, session: DatabaseSession) -> FundEventResponse:
    try:
        return allocate_funds(session, payload)
    except (
        AccountReferenceError,
        FundNotFoundError,
        FundCoverageError,
        FundBalanceError,
        FundTargetCapacityError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post(
    "/redistributions", response_model=FundEventResponse, status_code=status.HTTP_201_CREATED
)
def redistribute(
    payload: RedistributionCreateRequest, session: DatabaseSession
) -> FundEventResponse:
    try:
        return redistribute_fund(session, payload)
    except (AccountReferenceError, FundNotFoundError, FundCoverageError, FundBalanceError) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post(
    "/transfers", response_model=FundEventResponse, status_code=status.HTTP_201_CREATED
)
def transfer_fund(
    payload: FundTransferCreateRequest, session: DatabaseSession
) -> FundEventResponse:
    try:
        return transfer_between_funds(session, payload)
    except (AccountReferenceError, FundNotFoundError, FundBalanceError) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post(
    "/reserve-release", response_model=FundEventResponse, status_code=status.HTTP_201_CREATED
)
def release_reserve_to_free(
    payload: FundReserveReleaseRequest, session: DatabaseSession
) -> FundEventResponse:
    try:
        return release_fund_reserve(session, payload)
    except (AccountReferenceError, FundReserveBalanceError) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post(
    "/transfer-and-allocate",
    response_model=TransferAllocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def transfer_allocation(
    payload: TransferAllocationCreateRequest, session: DatabaseSession
) -> TransferAllocationResponse:
    try:
        return transfer_and_allocate(session, payload)
    except (
        AccountReferenceError,
        FundNotFoundError,
        FundAllocationUnavailableError,
        FundCoverageError,
        FundBalanceError,
        FundTargetCapacityError,
        InsufficientBalanceError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post("/releases", response_model=FundReleaseResponse, status_code=201)
def withdraw_fund(payload: FundReleaseRequest, session: DatabaseSession) -> FundReleaseResponse:
    try:
        return release_fund(session, payload)
    except (
        AccountReferenceError,
        FundNotFoundError,
        FundConflictError,
        FundBalanceError,
        FundCoverageError,
        InsufficientBalanceError,
        FutureOperationDateError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error
