from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.database import DatabaseSession
from app.modules.accounts.contracts import AccountReferenceError
from app.modules.categories.contracts import CategoryReferenceError
from app.modules.funds.contracts import (
    FundArchivedMutationError,
    FundBalanceError,
    FundCoverageError,
    FundNotFoundError,
)
from app.modules.operations.models import OperationType
from app.modules.operations.schemas import (
    CategorySummaryResponse,
    OperationCreateRequest,
    OperationPageResponse,
    OperationResponse,
    OperationUpdateRequest,
)
from app.modules.operations.service import (
    FutureOperationDateError,
    InsufficientBalanceError,
    OperationAllocationLinkedError,
    OperationConflictError,
    OperationDepreciationLinkedError,
    OperationFundReleaseLinkedError,
    OperationLinkedError,
    OperationNotFoundError,
    category_summary,
    create_operation,
    delete_operation,
    get_operation_response,
    list_operation_responses,
    reject_future_operation_date,
    update_operation,
)

read_router = APIRouter(prefix="/operations", tags=["operations"])
write_router = APIRouter(prefix="/operations", tags=["operations"])


def _raise_domain_error(error: RuntimeError) -> None:
    if isinstance(error, OperationNotFoundError):
        raise HTTPException(
            404, detail={"code": "operation_not_found", "message": "Operation not found"}
        )
    if isinstance(error, OperationConflictError):
        raise HTTPException(
            409, detail={"code": "operation_conflict", "message": "Operation was changed"}
        )
    if isinstance(error, FutureOperationDateError):
        raise HTTPException(
            422,
            detail={
                "code": "future_operation_requires_plan",
                "message": "Future operations must be created as plans",
            },
        )
    if isinstance(error, OperationLinkedError):
        raise HTTPException(
            409,
            detail={
                "code": "operation_linked_to_occurrence",
                "message": "Confirmed scheduled operation cannot be deleted",
            },
        )
    if isinstance(error, OperationDepreciationLinkedError):
        raise HTTPException(409, detail={"code": "operation_depreciation_linked"})
    if isinstance(error, OperationFundReleaseLinkedError):
        raise HTTPException(
            409,
            detail={
                "code": "operation_fund_release_linked",
                "message": "Delete and recreate this fund release transfer to change it",
            },
        )
    if isinstance(error, OperationAllocationLinkedError):
        raise HTTPException(
            409,
            detail={
                "code": "operation_linked_to_allocation",
                "message": "Transfer with fund allocation must be deleted and recreated",
            },
        )
    if isinstance(error, InsufficientBalanceError):
        raise HTTPException(
            409, detail={"code": "insufficient_balance", "message": "Insufficient balance"}
        )
    if isinstance(error, AccountReferenceError):
        raise HTTPException(
            409,
            detail={"code": "invalid_account_reference", "message": "Account is unavailable"},
        )
    if isinstance(error, CategoryReferenceError):
        raise HTTPException(
            409,
            detail={"code": "invalid_category_reference", "message": "Category is unavailable"},
        )
    if isinstance(error, FundNotFoundError):
        raise HTTPException(
            409, detail={"code": "invalid_fund_reference", "message": "Fund is unavailable"}
        )
    if isinstance(error, FundArchivedMutationError):
        raise HTTPException(
            409,
            detail={
                "code": "archived_fund_balance",
                "message": "Operation would restore a balance in an archived fund",
            },
        )
    if isinstance(error, FundBalanceError):
        raise HTTPException(
            409,
            detail={"code": "insufficient_fund_balance", "message": "Insufficient fund balance"},
        )
    if isinstance(error, FundCoverageError):
        raise HTTPException(
            409,
            detail={"code": "insufficient_free_balance", "message": "Fund coverage is invalid"},
        )
    raise error


@read_router.get("", response_model=OperationPageResponse)
def read_operations(
    session: DatabaseSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    occurred_from: date | None = None,
    occurred_to: date | None = None,
    account_id: UUID | None = None,
    type: OperationType | None = None,
    category_id: UUID | None = None,
) -> OperationPageResponse:
    return list_operation_responses(
        session,
        page=page,
        page_size=page_size,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        account_id=account_id,
        operation_type=type,
        category_id=category_id,
    )


@read_router.get("/category-summary", response_model=CategorySummaryResponse)
def read_category_summary(
    session: DatabaseSession, from_on: date, through_on: date
) -> CategorySummaryResponse:
    if through_on < from_on:
        raise HTTPException(422, detail={"code": "invalid_period", "message": "Invalid period"})
    return category_summary(session, from_on=from_on, through_on=through_on)


@read_router.get("/{operation_id}", response_model=OperationResponse)
def read_operation(operation_id: UUID, session: DatabaseSession) -> OperationResponse:
    try:
        return get_operation_response(session, operation_id)
    except OperationNotFoundError as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post("", response_model=OperationResponse, status_code=status.HTTP_201_CREATED)
def add_operation(payload: OperationCreateRequest, session: DatabaseSession) -> OperationResponse:
    try:
        reject_future_operation_date(session, payload.occurred_on)
        operation = create_operation(session, payload)
        return get_operation_response(session, operation.id)
    except (
        AccountReferenceError,
        CategoryReferenceError,
        FundBalanceError,
        FundArchivedMutationError,
        FundCoverageError,
        FundNotFoundError,
        InsufficientBalanceError,
        FutureOperationDateError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.put("/{operation_id}", response_model=OperationResponse)
def replace_operation(
    operation_id: UUID, payload: OperationUpdateRequest, session: DatabaseSession
) -> OperationResponse:
    try:
        reject_future_operation_date(session, payload.occurred_on)
        operation = update_operation(
            session, operation_id, payload, expected_version=payload.version
        )
        return get_operation_response(session, operation.id)
    except (
        AccountReferenceError,
        CategoryReferenceError,
        FundBalanceError,
        FundArchivedMutationError,
        FundCoverageError,
        FundNotFoundError,
        InsufficientBalanceError,
        OperationAllocationLinkedError,
        OperationDepreciationLinkedError,
        OperationFundReleaseLinkedError,
        OperationConflictError,
        OperationNotFoundError,
        FutureOperationDateError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.delete("/{operation_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_operation(
    operation_id: UUID,
    session: DatabaseSession,
    version: int = Query(ge=1),
) -> Response:
    try:
        delete_operation(session, operation_id, expected_version=version)
    except (
        AccountReferenceError,
        FundBalanceError,
        FundArchivedMutationError,
        FundCoverageError,
        FundNotFoundError,
        InsufficientBalanceError,
        OperationConflictError,
        OperationLinkedError,
        OperationDepreciationLinkedError,
        OperationNotFoundError,
    ) as error:
        _raise_domain_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
