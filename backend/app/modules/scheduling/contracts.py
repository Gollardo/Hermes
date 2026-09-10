"""Public scheduling references used by cross-module read/application use cases."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.operations.contracts import OperationType
from app.modules.operations.schemas import OperationCreateRequest
from app.modules.scheduling.models import (
    ExpectedOccurrence,
    OccurrenceSourceKind,
    OccurrenceStatus,
    RecurringRule,
)

if TYPE_CHECKING:
    from app.modules.scheduling.schemas import ExpectedOccurrenceResponse


@dataclass(frozen=True, slots=True)
class OccurrenceConfirmationDraft:
    type: OperationType
    occurred_on: date
    amount: Decimal
    description: str | None
    account_id: UUID
    destination_account_id: UUID | None
    category_id: UUID | None
    allocate_to_funds: bool


@dataclass(frozen=True, slots=True)
class OccurrenceConfirmationOverride:
    type: OperationType
    amount: Decimal
    description: str | None
    account_id: UUID
    destination_account_id: UUID | None
    category_id: UUID | None
    allocate_to_funds: bool


OccurrencePoster = Callable[[OccurrenceConfirmationDraft], UUID]


def confirm_occurrence(
    session: Session,
    occurrence_id: UUID,
    *,
    expected_version: int,
    amount: Decimal | None,
    override: OccurrenceConfirmationOverride | None,
    poster: OccurrencePoster,
) -> "ExpectedOccurrenceResponse":
    """Confirm through Scheduling while the supplied poster owns financial orchestration."""
    from app.modules.scheduling.service import confirm_occurrence as _confirm_occurrence

    return _confirm_occurrence(
        session,
        occurrence_id,
        expected_version=expected_version,
        amount=amount,
        override=override,
        poster=poster,
    )


@dataclass(frozen=True, slots=True)
class PlannedOccurrence:
    id: UUID
    rule_id: UUID | None
    due_on: date
    type: OperationType
    amount: Decimal
    description: str | None
    account_id: UUID
    destination_account_id: UUID | None
    allocate_to_funds: bool
    status: OccurrenceStatus
    source_kind: OccurrenceSourceKind = OccurrenceSourceKind.RECURRING


@dataclass(frozen=True, slots=True)
class ForecastScheduleSnapshot:
    occurrences: list[PlannedOccurrence]
    overdue_count: int
    overdue_count_by_account: dict[UUID, int] = field(default_factory=dict)


def forecast_schedule_snapshot(
    session: Session,
    *,
    today: date,
    due_to: date,
    account_id: UUID | None,
) -> ForecastScheduleSnapshot:
    """Lock and return one consistent actionable schedule snapshot.

    The shared row locks serialize confirmation, cancellation and postponement
    until the caller has read the ledger balance in the same transaction. This
    prevents a confirming occurrence from appearing in both actual and planned
    money in one forecast.
    """
    conditions = [
        ExpectedOccurrence.due_on <= due_to,
        ExpectedOccurrence.status.in_({OccurrenceStatus.PENDING, OccurrenceStatus.POSTPONED}),
    ]
    if account_id is not None:
        conditions.append(
            or_(
                ExpectedOccurrence.account_id == account_id,
                ExpectedOccurrence.destination_account_id == account_id,
            )
        )
    occurrences = session.scalars(
        select(ExpectedOccurrence)
        .where(*conditions)
        .order_by(
            ExpectedOccurrence.rule_id,
            ExpectedOccurrence.scheduled_on,
            ExpectedOccurrence.id,
        )
        .with_for_update(read=True)
    ).all()
    planned = sorted(
        [
            PlannedOccurrence(
                id=item.id,
                source_kind=item.source_kind,
                rule_id=item.rule_id,
                due_on=item.due_on,
                type=item.type,
                amount=Decimal(item.amount),
                description=item.description,
                account_id=item.account_id,
                destination_account_id=item.destination_account_id,
                allocate_to_funds=item.allocate_to_funds,
                status=item.status,
            )
            for item in occurrences
            if item.due_on >= today
        ],
        key=lambda item: (item.due_on, item.id),
    )
    overdue_count_by_account: dict[UUID, int] = {}
    for item in occurrences:
        if item.due_on >= today:
            continue
        affected = {item.account_id}
        if item.destination_account_id is not None:
            affected.add(item.destination_account_id)
        for affected_account_id in affected:
            overdue_count_by_account[affected_account_id] = (
                overdue_count_by_account.get(affected_account_id, 0) + 1
            )
    return ForecastScheduleSnapshot(
        occurrences=planned,
        overdue_count=sum(item.due_on < today for item in occurrences),
        overdue_count_by_account=overdue_count_by_account,
    )


def account_has_schedule_reference(session: Session, account_id: UUID) -> bool:
    return (
        session.scalar(
            select(RecurringRule.id)
            .where(
                or_(
                    RecurringRule.account_id == account_id,
                    RecurringRule.destination_account_id == account_id,
                )
            )
            .limit(1)
        )
        is not None
        or session.scalar(
            select(ExpectedOccurrence.id)
            .where(
                or_(
                    ExpectedOccurrence.account_id == account_id,
                    ExpectedOccurrence.destination_account_id == account_id,
                )
            )
            .limit(1)
        )
        is not None
    )


def category_has_schedule_reference(session: Session, category_id: UUID) -> bool:
    return (
        session.scalar(
            select(RecurringRule.id).where(RecurringRule.category_id == category_id).limit(1)
        )
        is not None
        or session.scalar(
            select(ExpectedOccurrence.id)
            .where(ExpectedOccurrence.category_id == category_id)
            .limit(1)
        )
        is not None
    )


def has_schedule_data(session: Session) -> bool:
    """Return whether calendar-date semantics have become persistent."""
    return (
        session.scalar(select(RecurringRule.id).limit(1)) is not None
        or session.scalar(select(ExpectedOccurrence.id).limit(1)) is not None
    )


__all__ = [
    "import_plan_candidates",
    "confirm_imported_occurrence",
    "lock_import_occurrences",
    "ForecastScheduleSnapshot",
    "OccurrenceConfirmationDraft",
    "OccurrenceConfirmationOverride",
    "OccurrencePoster",
    "OccurrenceSourceKind",
    "OccurrenceStatus",
    "PlannedOccurrence",
    "account_has_schedule_reference",
    "category_has_schedule_reference",
    "confirm_occurrence",
    "forecast_schedule_snapshot",
    "has_schedule_data",
]


def import_plan_candidates(
    session: Session, account_id: UUID, from_on: date, through_on: date
) -> list[dict[str, object]]:
    rows = session.scalars(
        select(ExpectedOccurrence)
        .where(
            or_(
                ExpectedOccurrence.account_id == account_id,
                ExpectedOccurrence.destination_account_id == account_id,
            ),
            ExpectedOccurrence.due_on.between(from_on, through_on),
            ExpectedOccurrence.status.in_([OccurrenceStatus.PENDING, OccurrenceStatus.POSTPONED]),
        )
        .order_by(ExpectedOccurrence.due_on, ExpectedOccurrence.id)
        .limit(1001)
    ).all()
    if len(rows) > 1000:
        raise ValueError("Too many plans; narrow the date window")
    return [
        dict(
            id=str(o.id),
            version=o.version,
            type=o.type.value,
            direction="income"
            if o.destination_account_id == account_id or o.type == OperationType.INCOME
            else "expense",
            amount=str(o.amount),
            date=o.due_on.isoformat(),
            description=o.description or "",
            category_id=str(o.category_id) if o.category_id else None,
            account_id=str(o.account_id),
            destination_account_id=str(o.destination_account_id)
            if o.destination_account_id
            else None,
            allocate_to_funds=o.allocate_to_funds,
        )
        for o in rows
    ]


def confirm_imported_occurrence(
    session: Session,
    occurrence_id: UUID,
    version: int,
    operation_id: UUID,
    payload: "OperationCreateRequest",
    allocate_to_funds: bool,
) -> None:
    from datetime import UTC, datetime

    occurrence = session.scalar(
        select(ExpectedOccurrence).where(ExpectedOccurrence.id == occurrence_id).with_for_update()
    )
    if (
        occurrence is None
        or occurrence.version != version
        or occurrence.status not in {OccurrenceStatus.PENDING, OccurrenceStatus.POSTPONED}
    ):
        raise ValueError("Plan changed or is no longer actionable")
    linked = session.scalar(
        select(ExpectedOccurrence.id).where(ExpectedOccurrence.actual_operation_id == operation_id)
    )
    if linked is not None:
        raise ValueError("Operation already linked to a plan")
    occurrence.type = payload.type
    occurrence.amount = payload.amount
    occurrence.description = payload.description
    occurrence.account_id = payload.account_id
    occurrence.destination_account_id = payload.destination_account_id
    occurrence.category_id = payload.category_id
    occurrence.allocate_to_funds = allocate_to_funds
    occurrence.status = OccurrenceStatus.CONFIRMED
    occurrence.actual_operation_id = operation_id
    occurrence.manually_modified = True
    occurrence.version += 1
    occurrence.updated_at = datetime.now(UTC)
    session.flush()


def lock_import_occurrences(session: Session, ids: set[UUID]) -> None:
    session.scalars(
        select(ExpectedOccurrence)
        .where(ExpectedOccurrence.id.in_(ids))
        .order_by(ExpectedOccurrence.id)
        .with_for_update()
    ).all()
