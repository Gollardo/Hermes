from decimal import ROUND_DOWN, Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.database import DatabaseSession
from app.modules.accounts.contracts import AccountReferenceError
from app.modules.depreciation import service
from app.modules.depreciation.calculation import inflation_target
from app.modules.depreciation.schemas import (
    ContributionCreate,
    LifecycleRequest,
    PurchaseCreate,
    PurchaseResponse,
)
from app.modules.funds.contracts import (
    FundArchiveBalanceError,
    FundBalanceError,
    FundConflictError,
    FundCoverageError,
    FundNotFoundError,
    FundTargetCapacityError,
)
from app.modules.operations.contracts import InsufficientBalanceError

read_router = APIRouter(prefix="/depreciation", tags=["depreciation"])
write_router = APIRouter(prefix="/depreciation", tags=["depreciation"])


def domain_error(error: RuntimeError) -> HTTPException:
    if isinstance(error, service.DepreciationError):
        return HTTPException(error.status, detail={"code": error.code})
    codes = {
        AccountReferenceError: "invalid_account_reference",
        FundNotFoundError: "fund_not_found",
        FundBalanceError: "insufficient_fund_balance",
        FundCoverageError: "insufficient_free_balance",
        FundConflictError: "depreciation_conflict",
        FundTargetCapacityError: "fund_target_capacity",
        FundArchiveBalanceError: "fund_has_balance",
        InsufficientBalanceError: "insufficient_balance",
    }
    for kind, code in codes.items():
        if isinstance(error, kind):
            return HTTPException(409, detail={"code": code})
    raise error


@read_router.get("", response_model=list[PurchaseResponse])
def listing(session: DatabaseSession) -> list[PurchaseResponse]:
    return service.list_purchases(session)


@write_router.post("", response_model=PurchaseResponse, status_code=201)
def create(payload: PurchaseCreate, session: DatabaseSession) -> PurchaseResponse:
    try:
        return service.create_purchase(session, payload)
    except RuntimeError as error:
        raise domain_error(error) from error


@write_router.post("/{purchase_id}/contributions", response_model=PurchaseResponse)
def contribute(
    purchase_id: UUID, payload: ContributionCreate, session: DatabaseSession
) -> PurchaseResponse:
    try:
        return service.contribute(session, purchase_id, payload)
    except RuntimeError as error:
        raise domain_error(error) from error


@write_router.post("/{purchase_id}/archive", response_model=PurchaseResponse)
def archive(
    purchase_id: UUID, payload: LifecycleRequest, session: DatabaseSession
) -> PurchaseResponse:
    try:
        return service.archive_purchase(session, purchase_id, payload.version)
    except RuntimeError as error:
        raise domain_error(error) from error


@write_router.post("/preview")
def preview(payload: PurchaseCreate) -> dict[str, str]:
    target = inflation_target(payload.cost, payload.inflation, payload.months)
    return {
        "target": format(target, "f"),
        "monthly": format(
            (target / payload.months).quantize(Decimal("0.0001"), rounding=ROUND_DOWN), "f"
        ),
    }
