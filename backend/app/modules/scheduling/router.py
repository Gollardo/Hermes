from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.application.scheduling import confirm_expected_occurrence
from app.core.database import DatabaseSession
from app.modules.accounts.contracts import AccountReferenceError
from app.modules.categories.contracts import CategoryReferenceError
from app.modules.funds.contracts import (
    FundAllocationUnavailableError,
    FundBalanceError,
    FundCoverageError,
)
from app.modules.operations.contracts import (
    FutureOperationDateError,
    InsufficientBalanceError,
    OperationType,
)
from app.modules.scheduling.models import OccurrenceSourceKind, OccurrenceStatus
from app.modules.scheduling.schemas import (
    ExpectedOccurrenceResponse,
    MaterializationResponse,
    OccurrenceConfirmRequest,
    OccurrencePageResponse,
    OccurrencePostponeRequest,
    OccurrencePostponeResponse,
    OccurrenceVersionRequest,
    OneOffPlanCreateRequest,
    OneOffPlanUpdateRequest,
    RecurringRuleCreateRequest,
    RecurringRuleResponse,
    RecurringRuleUpdateRequest,
)
from app.modules.scheduling.service import (
    ExpectedOccurrenceNotFoundError,
    InvalidOccurrenceTransitionError,
    RecurringRuleNotFoundError,
    SchedulingConflictError,
    cancel_occurrence,
    create_one_off_plan,
    create_rule,
    get_occurrence_response,
    get_rule_response,
    list_occurrence_responses,
    list_rule_responses,
    materialize_all,
    postpone_occurrence,
    update_one_off_plan,
    update_rule,
)

read_router = APIRouter(prefix="/scheduling", tags=["scheduling"])
write_router = APIRouter(prefix="/scheduling", tags=["scheduling"])


def _raise_domain_error(error: RuntimeError) -> None:
    if isinstance(error, FutureOperationDateError):
        raise HTTPException(422, detail={"code": "future_operation_requires_plan"})
    if isinstance(error, RecurringRuleNotFoundError):
        raise HTTPException(
            404, detail={"code": "recurring_rule_not_found", "message": "Rule not found"}
        )
    if isinstance(error, ExpectedOccurrenceNotFoundError):
        raise HTTPException(
            404,
            detail={"code": "expected_occurrence_not_found", "message": "Occurrence not found"},
        )
    if isinstance(error, SchedulingConflictError):
        raise HTTPException(
            409,
            detail={"code": "scheduling_conflict", "message": "Schedule was changed"},
        )
    if isinstance(error, InvalidOccurrenceTransitionError):
        raise HTTPException(
            409,
            detail={
                "code": "invalid_occurrence_transition",
                "message": "Occurrence cannot perform this transition",
            },
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
    if isinstance(error, InsufficientBalanceError):
        raise HTTPException(
            409, detail={"code": "insufficient_balance", "message": "Insufficient balance"}
        )
    if isinstance(error, FundCoverageError):
        raise HTTPException(
            409,
            detail={"code": "insufficient_free_balance", "message": "Fund coverage is invalid"},
        )
    if isinstance(error, FundAllocationUnavailableError):
        raise HTTPException(
            409,
            detail={
                "code": "fund_allocation_unavailable",
                "message": "No fund allocation is configured",
            },
        )
    if isinstance(error, FundBalanceError):
        raise HTTPException(
            409,
            detail={"code": "insufficient_fund_balance", "message": "Fund balance is invalid"},
        )
    raise error


@read_router.get("/rules", response_model=list[RecurringRuleResponse])
def read_rules(session: DatabaseSession) -> list[RecurringRuleResponse]:
    return list_rule_responses(session)


@read_router.get("/occurrences", response_model=OccurrencePageResponse)
def read_occurrences(
    session: DatabaseSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=367),
    due_from: date | None = None,
    due_to: date | None = None,
    account_id: UUID | None = None,
    type: OperationType | None = None,
    statuses: Annotated[list[OccurrenceStatus] | None, Query(alias="status")] = None,
    source_kinds: Annotated[list[OccurrenceSourceKind] | None, Query(alias="source_kind")] = None,
) -> OccurrencePageResponse:
    return list_occurrence_responses(
        session,
        page=page,
        page_size=page_size,
        due_from=due_from,
        due_to=due_to,
        account_id=account_id,
        operation_type=type,
        statuses=set(statuses) if statuses else None,
        source_kinds=set(source_kinds) if source_kinds else None,
    )


@read_router.get("/occurrences/{occurrence_id}", response_model=ExpectedOccurrenceResponse)
def read_occurrence(occurrence_id: UUID, session: DatabaseSession) -> ExpectedOccurrenceResponse:
    try:
        return get_occurrence_response(session, occurrence_id)
    except ExpectedOccurrenceNotFoundError as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post(
    "/rules", response_model=RecurringRuleResponse, status_code=status.HTTP_201_CREATED
)
def add_rule(
    payload: RecurringRuleCreateRequest, session: DatabaseSession
) -> RecurringRuleResponse:
    try:
        rule = create_rule(session, payload)
        return get_rule_response(session, rule.id)
    except (AccountReferenceError, CategoryReferenceError) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post(
    "/one-off-plans", response_model=ExpectedOccurrenceResponse, status_code=status.HTTP_201_CREATED
)
def add_one_off_plan(
    payload: OneOffPlanCreateRequest, session: DatabaseSession
) -> ExpectedOccurrenceResponse:
    try:
        occurrence = create_one_off_plan(session, payload)
        return get_occurrence_response(session, occurrence.id)
    except (AccountReferenceError, CategoryReferenceError) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.put("/one-off-plans/{occurrence_id}", response_model=ExpectedOccurrenceResponse)
def replace_one_off_plan(
    occurrence_id: UUID, payload: OneOffPlanUpdateRequest, session: DatabaseSession
) -> ExpectedOccurrenceResponse:
    try:
        occurrence = update_one_off_plan(session, occurrence_id, payload)
        return get_occurrence_response(session, occurrence.id)
    except (
        AccountReferenceError,
        CategoryReferenceError,
        ExpectedOccurrenceNotFoundError,
        InvalidOccurrenceTransitionError,
        SchedulingConflictError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.put("/rules/{rule_id}", response_model=RecurringRuleResponse)
def replace_rule(
    rule_id: UUID, payload: RecurringRuleUpdateRequest, session: DatabaseSession
) -> RecurringRuleResponse:
    try:
        rule = update_rule(session, rule_id, payload)
        return get_rule_response(session, rule.id)
    except (
        AccountReferenceError,
        CategoryReferenceError,
        RecurringRuleNotFoundError,
        SchedulingConflictError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post("/materialize", response_model=MaterializationResponse)
def materialize(session: DatabaseSession) -> MaterializationResponse:
    return materialize_all(session)


@write_router.post(
    "/occurrences/{occurrence_id}/confirm", response_model=ExpectedOccurrenceResponse
)
def confirm(
    occurrence_id: UUID, payload: OccurrenceConfirmRequest, session: DatabaseSession
) -> ExpectedOccurrenceResponse:
    try:
        return confirm_expected_occurrence(
            session,
            occurrence_id,
            expected_version=payload.version,
            amount=payload.amount,
            occurred_on=payload.occurred_on,
            operation=payload.operation,
        )
    except (
        FutureOperationDateError,
        AccountReferenceError,
        CategoryReferenceError,
        ExpectedOccurrenceNotFoundError,
        FundCoverageError,
        FundAllocationUnavailableError,
        FundBalanceError,
        InsufficientBalanceError,
        InvalidOccurrenceTransitionError,
        SchedulingConflictError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post(
    "/occurrences/{occurrence_id}/postpone", response_model=OccurrencePostponeResponse
)
def postpone(
    occurrence_id: UUID, payload: OccurrencePostponeRequest, session: DatabaseSession
) -> OccurrencePostponeResponse:
    try:
        return postpone_occurrence(
            session,
            occurrence_id,
            due_on=payload.due_on,
            expected_version=payload.version,
            expected_rule_version=payload.rule_version,
        )
    except (
        ExpectedOccurrenceNotFoundError,
        InvalidOccurrenceTransitionError,
        SchedulingConflictError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error


@write_router.post("/occurrences/{occurrence_id}/cancel", response_model=ExpectedOccurrenceResponse)
def cancel(
    occurrence_id: UUID, payload: OccurrenceVersionRequest, session: DatabaseSession
) -> ExpectedOccurrenceResponse:
    try:
        return cancel_occurrence(session, occurrence_id, expected_version=payload.version)
    except (
        ExpectedOccurrenceNotFoundError,
        InvalidOccurrenceTransitionError,
        SchedulingConflictError,
    ) as error:
        _raise_domain_error(error)
        raise AssertionError from error
