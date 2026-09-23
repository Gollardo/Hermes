from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.modules.accounts.contracts import account_names, lock_account_references
from app.modules.categories.contracts import (
    CategoryType,
    category_name,
    validate_category_reference,
)
from app.modules.operations.contracts import (
    FutureOperationDateError,
    OperationType,
    operation_history_references,
)
from app.modules.scheduling.contracts import (
    OccurrenceConfirmationDraft,
    OccurrenceConfirmationOverride,
    OccurrencePoster,
)
from app.modules.scheduling.models import (
    ExpectedOccurrence,
    OccurrenceSourceKind,
    OccurrenceStatus,
    RecurrenceFrequency,
    RecurringRule,
)
from app.modules.scheduling.schemas import (
    ExpectedOccurrenceResponse,
    MaterializationResponse,
    OccurrencePageResponse,
    OccurrencePostponeResponse,
    OneOffPlanCreateRequest,
    OneOffPlanUpdateRequest,
    RecurringRuleCreateRequest,
    RecurringRuleResponse,
    RecurringRuleUpdateRequest,
    format_money,
)
from app.modules.settings.contracts import application_timezone, lock_application_timezone


class RecurringRuleNotFoundError(RuntimeError):
    pass


class SchedulingConflictError(RuntimeError):
    pass


class ExpectedOccurrenceNotFoundError(RuntimeError):
    pass


class InvalidOccurrenceTransitionError(RuntimeError):
    pass


@dataclass(slots=True)
class _MaterializationCounts:
    created: int = 0
    updated: int = 0
    cancelled: int = 0

    def add(self, other: "_MaterializationCounts") -> None:
        self.created += other.created
        self.updated += other.updated
        self.cancelled += other.cancelled


def calendar_year_later(value: date) -> date:
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return value.replace(year=value.year + 1, day=28)


def recurrence_dates(
    *,
    frequency: RecurrenceFrequency,
    interval: int = 1,
    weekdays: list[int] | None = None,
    anchor: date,
    range_from: date,
    range_to: date,
    end_on: date | None,
) -> list[date]:
    """Return deterministic recurrence dates within an inclusive bounded range."""
    upper = min(range_to, end_on) if end_on is not None else range_to
    lower = max(range_from, anchor)
    if upper < lower:
        return []
    if frequency == RecurrenceFrequency.DAILY:
        step = 1
        elapsed = (lower - anchor).days
        skipped = (elapsed + step - 1) // step
        current = anchor + timedelta(days=skipped * step)
        result: list[date] = []
        while current <= upper:
            result.append(current)
            current += timedelta(days=step)
        return result
    if frequency == RecurrenceFrequency.WEEKLY:
        selected = sorted(weekdays or [anchor.isoweekday()])
        anchor_week = anchor - timedelta(days=anchor.isoweekday() - 1)
        current_week = lower - timedelta(days=lower.isoweekday() - 1)
        elapsed_weeks = (current_week - anchor_week).days // 7
        if elapsed_weeks % interval:
            current_week += timedelta(weeks=interval - elapsed_weeks % interval)
        result = []
        while current_week <= upper:
            for weekday in selected:
                current = current_week + timedelta(days=weekday - 1)
                if current >= anchor and lower <= current <= upper:
                    result.append(current)
            current_week += timedelta(weeks=interval)
        return result
    if frequency == RecurrenceFrequency.MONTHLY:
        start_index = anchor.year * 12 + anchor.month - 1
        lower_index = lower.year * 12 + lower.month - 1
        index = max(start_index, lower_index)
        remainder = (index - start_index) % interval
        if remainder:
            index += interval - remainder
        current = date(index // 12, index % 12 + 1, anchor.day)
        if current < lower:
            index += interval
        result = []
        while True:
            current = date(index // 12, index % 12 + 1, anchor.day)
            if current > upper:
                return result
            result.append(current)
            index += interval
    year = max(anchor.year, lower.year)
    current = date(year, anchor.month, anchor.day)
    if current < lower:
        year += interval
    result = []
    while True:
        current = date(year, anchor.month, anchor.day)
        if current > upper:
            return result
        result.append(current)
        year += interval


def _today(session: Session) -> date:
    return datetime.now(UTC).astimezone(ZoneInfo(application_timezone(session))).date()


def _validate_schedule_references(
    session: Session,
    payload: (
        RecurringRuleCreateRequest | OneOffPlanCreateRequest | OccurrenceConfirmationOverride
    ),
    *,
    require_active: bool,
) -> None:
    if payload.category_id is not None:
        expected_type = (
            CategoryType.INCOME if payload.type == OperationType.INCOME else CategoryType.EXPENSE
        )
        validate_category_reference(
            session,
            payload.category_id,
            expected_type=expected_type,
            allow_archived=not require_active,
        )
    account_ids = {payload.account_id}
    if payload.destination_account_id is not None:
        account_ids.add(payload.destination_account_id)
    lock_account_references(
        session,
        account_ids,
        allow_archived_ids=set() if require_active else account_ids,
    )


def _get_rule(session: Session, rule_id: UUID, *, lock: bool) -> RecurringRule:
    query = select(RecurringRule).where(RecurringRule.id == rule_id)
    if lock:
        query = query.with_for_update()
    rule = session.scalar(query)
    if rule is None:
        raise RecurringRuleNotFoundError
    return rule


def _get_occurrence(session: Session, occurrence_id: UUID, *, lock: bool) -> ExpectedOccurrence:
    query = select(ExpectedOccurrence).where(ExpectedOccurrence.id == occurrence_id)
    if lock:
        query = query.with_for_update()
    occurrence = session.scalar(query)
    if occurrence is None:
        raise ExpectedOccurrenceNotFoundError
    return occurrence


def _copy_snapshot(rule: RecurringRule, occurrence: ExpectedOccurrence) -> bool:
    changed = False
    values: dict[str, object] = {
        "type": rule.type,
        "amount": rule.amount,
        "description": rule.description,
        "account_id": rule.account_id,
        "destination_account_id": rule.destination_account_id,
        "category_id": rule.category_id,
        "allocate_to_funds": rule.allocate_to_funds,
    }
    for name, value in values.items():
        if getattr(occurrence, name) != value:
            setattr(occurrence, name, value)
            changed = True
    return changed


def _shift_date(value: date, days: int) -> date:
    try:
        return value + timedelta(days=days)
    except OverflowError as error:
        raise InvalidOccurrenceTransitionError from error


def _new_occurrence(rule: RecurringRule, scheduled_on: date, now: datetime) -> ExpectedOccurrence:
    return ExpectedOccurrence(
        source_kind=OccurrenceSourceKind.RECURRING,
        rule_id=rule.id,
        scheduled_on=scheduled_on,
        due_on=_shift_date(scheduled_on, rule.series_shift_days),
        status=OccurrenceStatus.PENDING,
        manually_modified=False,
        series_shift_days=rule.series_shift_days,
        preserve_from_series_shift=False,
        type=rule.type,
        amount=rule.amount,
        description=rule.description,
        account_id=rule.account_id,
        destination_account_id=rule.destination_account_id,
        category_id=rule.category_id,
        allocate_to_funds=rule.allocate_to_funds,
        actual_operation_id=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _lock_rule_occurrences(session: Session, rule_id: UUID) -> dict[date, ExpectedOccurrence]:
    return {
        occurrence.scheduled_on: occurrence
        for occurrence in session.scalars(
            select(ExpectedOccurrence)
            .where(ExpectedOccurrence.rule_id == rule_id)
            .order_by(ExpectedOccurrence.scheduled_on, ExpectedOccurrence.id)
            .with_for_update()
        ).all()
    }


def _lock_series_shift_candidates(
    session: Session, rule_id: UUID, *, after_scheduled_on: date
) -> list[ExpectedOccurrence]:
    return list(
        session.scalars(
            select(ExpectedOccurrence)
            .where(
                ExpectedOccurrence.rule_id == rule_id,
                ExpectedOccurrence.scheduled_on > after_scheduled_on,
                or_(
                    ExpectedOccurrence.status == OccurrenceStatus.PENDING,
                    and_(
                        ExpectedOccurrence.status == OccurrenceStatus.CANCELLED,
                        ExpectedOccurrence.manually_modified.is_(False),
                        ExpectedOccurrence.preserve_from_series_shift.is_(False),
                    ),
                ),
            )
            .order_by(ExpectedOccurrence.scheduled_on, ExpectedOccurrence.id)
            .with_for_update()
        ).all()
    )


def _materialization_dates(
    rule: RecurringRule, *, horizon_from: date, horizon_to: date
) -> set[date]:
    if not rule.active:
        return set()
    scheduled_range_from = _shift_date(horizon_from, -rule.series_shift_days)
    scheduled_range_to = _shift_date(horizon_to, -rule.series_shift_days)
    return set(
        recurrence_dates(
            frequency=rule.frequency,
            interval=rule.interval,
            weekdays=rule.weekdays,
            anchor=rule.start_on,
            range_from=scheduled_range_from,
            range_to=scheduled_range_to,
            end_on=rule.end_on,
        )
    )


def _materialize_missing_occurrences(
    session: Session,
    rule: RecurringRule,
    *,
    horizon_from: date,
    horizon_to: date,
    now: datetime,
) -> int:
    target_dates = _materialization_dates(
        rule,
        horizon_from=horizon_from,
        horizon_to=horizon_to,
    )
    existing_dates = set(
        session.scalars(
            select(ExpectedOccurrence.scheduled_on).where(ExpectedOccurrence.rule_id == rule.id)
        ).all()
    )
    missing_dates = target_dates - existing_dates
    for scheduled_on in sorted(missing_dates):
        session.add(_new_occurrence(rule, scheduled_on, now))
    return len(missing_dates)


def _synchronize_rule(
    session: Session,
    rule: RecurringRule,
    *,
    horizon_from: date,
    horizon_to: date,
    existing: dict[date, ExpectedOccurrence] | None = None,
) -> _MaterializationCounts:
    if existing is None:
        existing = _lock_rule_occurrences(session, rule.id)
    scheduled_range_from = _shift_date(horizon_from, -rule.series_shift_days)
    scheduled_range_to = _shift_date(horizon_to, -rule.series_shift_days)
    materialization_dates = _materialization_dates(
        rule,
        horizon_from=horizon_from,
        horizon_to=horizon_to,
    )
    now = datetime.now(UTC)
    counts = _MaterializationCounts()
    for scheduled_on, occurrence in existing.items():
        if occurrence.due_on < horizon_from:
            continue
        if occurrence.preserve_from_series_shift:
            continue
        if occurrence.status == OccurrenceStatus.CONFIRMED or occurrence.manually_modified:
            continue
        changed = False
        matches_rule = scheduled_on in materialization_dates
        if (
            rule.active
            and not matches_rule
            and (scheduled_on < scheduled_range_from or scheduled_on > scheduled_range_to)
        ):
            matches_rule = bool(
                recurrence_dates(
                    frequency=rule.frequency,
                    interval=rule.interval,
                    weekdays=rule.weekdays,
                    anchor=rule.start_on,
                    range_from=scheduled_on,
                    range_to=scheduled_on,
                    end_on=rule.end_on,
                )
            )
        if matches_rule:
            if occurrence.status != OccurrenceStatus.PENDING:
                occurrence.status = OccurrenceStatus.PENDING
                changed = True
            expected_due_on = _shift_date(scheduled_on, occurrence.series_shift_days)
            if occurrence.due_on != expected_due_on:
                occurrence.due_on = expected_due_on
                changed = True
            changed = _copy_snapshot(rule, occurrence) or changed
        elif occurrence.status != OccurrenceStatus.CANCELLED:
            occurrence.status = OccurrenceStatus.CANCELLED
            occurrence.due_on = _shift_date(scheduled_on, occurrence.series_shift_days)
            changed = True
            counts.cancelled += 1
        if changed:
            occurrence.version += 1
            occurrence.updated_at = now
            counts.updated += 1
    for scheduled_on in sorted(materialization_dates - existing.keys()):
        session.add(_new_occurrence(rule, scheduled_on, now))
        counts.created += 1
    session.flush()
    return counts


def create_rule(
    session: Session, payload: RecurringRuleCreateRequest, *, today: date | None = None
) -> RecurringRule:
    lock_application_timezone(session)
    _validate_schedule_references(session, payload, require_active=True)
    now = datetime.now(UTC)
    rule = RecurringRule(
        **payload.model_dump(), active=True, version=1, created_at=now, updated_at=now
    )
    session.add(rule)
    session.flush()
    horizon_from = today or _today(session)
    _synchronize_rule(
        session,
        rule,
        horizon_from=horizon_from,
        horizon_to=calendar_year_later(horizon_from),
    )
    return rule


def update_rule(
    session: Session,
    rule_id: UUID,
    payload: RecurringRuleUpdateRequest,
    *,
    today: date | None = None,
) -> RecurringRule:
    rule = _get_rule(session, rule_id, lock=True)
    if rule.version != payload.version:
        raise SchedulingConflictError
    existing = _lock_rule_occurrences(session, rule.id)
    _validate_schedule_references(session, payload, require_active=payload.active)
    for name, value in payload.model_dump(exclude={"version"}).items():
        setattr(rule, name, value)
    rule.version += 1
    rule.updated_at = datetime.now(UTC)
    horizon_from = today or _today(session)
    _synchronize_rule(
        session,
        rule,
        horizon_from=horizon_from,
        horizon_to=calendar_year_later(horizon_from),
        existing=existing,
    )
    return rule


def materialize_all(session: Session, *, today: date | None = None) -> MaterializationResponse:
    horizon_from = today or _today(session)
    horizon_to = calendar_year_later(horizon_from)
    counts = _MaterializationCounts()
    rules = session.scalars(
        select(RecurringRule).order_by(RecurringRule.id).with_for_update()
    ).all()
    for rule in rules:
        counts.add(
            _synchronize_rule(session, rule, horizon_from=horizon_from, horizon_to=horizon_to)
        )
    return MaterializationResponse(
        horizon_from=horizon_from,
        horizon_to=horizon_to,
        created=counts.created,
        updated=counts.updated,
        cancelled=counts.cancelled,
    )


def _rule_response(session: Session, rule: RecurringRule) -> RecurringRuleResponse:
    ids = {rule.account_id}
    if rule.destination_account_id is not None:
        ids.add(rule.destination_account_id)
    names = account_names(session, ids)
    return RecurringRuleResponse(
        id=rule.id,
        type=rule.type,
        frequency=rule.frequency,
        interval=rule.interval,
        weekdays=rule.weekdays,
        start_on=rule.start_on,
        end_on=rule.end_on,
        amount=format_money(Decimal(rule.amount)),
        description=rule.description,
        account_id=rule.account_id,
        account_name=names[rule.account_id],
        destination_account_id=rule.destination_account_id,
        destination_account_name=(
            names[rule.destination_account_id] if rule.destination_account_id is not None else None
        ),
        category_id=rule.category_id,
        category_name=(category_name(session, rule.category_id) if rule.category_id else None),
        allocate_to_funds=rule.allocate_to_funds,
        shift_future_on_postpone=rule.shift_future_on_postpone,
        series_shift_days=rule.series_shift_days,
        active=rule.active,
        version=rule.version,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def list_rule_responses(session: Session) -> list[RecurringRuleResponse]:
    return [
        _rule_response(session, rule)
        for rule in session.scalars(
            select(RecurringRule).order_by(
                RecurringRule.active.desc(), RecurringRule.start_on, RecurringRule.id
            )
        ).all()
    ]


def get_rule_response(session: Session, rule_id: UUID) -> RecurringRuleResponse:
    return _rule_response(session, _get_rule(session, rule_id, lock=False))


def create_one_off_plan(session: Session, payload: OneOffPlanCreateRequest) -> ExpectedOccurrence:
    """Create a plan snapshot without posting ledger or fund movements."""
    lock_application_timezone(session)
    _validate_schedule_references(session, payload, require_active=True)
    now = datetime.now(UTC)
    occurrence = ExpectedOccurrence(
        source_kind=OccurrenceSourceKind.ONE_OFF,
        rule_id=None,
        scheduled_on=payload.scheduled_on,
        due_on=payload.scheduled_on,
        status=OccurrenceStatus.PENDING,
        manually_modified=False,
        series_shift_days=0,
        preserve_from_series_shift=False,
        type=payload.type,
        amount=payload.amount,
        description=payload.description,
        account_id=payload.account_id,
        destination_account_id=payload.destination_account_id,
        category_id=payload.category_id,
        allocate_to_funds=payload.allocate_to_funds,
        actual_operation_id=None,
        version=1,
        created_at=now,
        updated_at=now,
    )
    session.add(occurrence)
    session.flush()
    return occurrence


def get_occurrence_response(session: Session, occurrence_id: UUID) -> ExpectedOccurrenceResponse:
    return _occurrence_response(
        session,
        _get_occurrence(session, occurrence_id, lock=False),
        today=_today(session),
    )


def update_one_off_plan(
    session: Session, occurrence_id: UUID, payload: OneOffPlanUpdateRequest
) -> ExpectedOccurrence:
    occurrence = _get_occurrence(session, occurrence_id, lock=True)
    if occurrence.source_kind != OccurrenceSourceKind.ONE_OFF:
        raise ExpectedOccurrenceNotFoundError
    if occurrence.version != payload.version:
        raise SchedulingConflictError
    if occurrence.status not in {OccurrenceStatus.PENDING, OccurrenceStatus.POSTPONED}:
        raise InvalidOccurrenceTransitionError
    _validate_schedule_references(session, payload, require_active=True)
    for name, value in payload.model_dump(exclude={"version"}).items():
        setattr(occurrence, name, value)
    occurrence.due_on = payload.scheduled_on
    occurrence.status = OccurrenceStatus.PENDING
    occurrence.manually_modified = False
    occurrence.series_shift_days = 0
    occurrence.preserve_from_series_shift = False
    occurrence.version += 1
    occurrence.updated_at = datetime.now(UTC)
    session.flush()
    return occurrence


def _occurrence_response(
    session: Session, occurrence: ExpectedOccurrence, *, today: date
) -> ExpectedOccurrenceResponse:
    ids = {occurrence.account_id}
    if occurrence.destination_account_id is not None:
        ids.add(occurrence.destination_account_id)
    names = account_names(session, ids)
    return ExpectedOccurrenceResponse(
        id=occurrence.id,
        source_kind=occurrence.source_kind,
        rule_id=occurrence.rule_id,
        scheduled_on=occurrence.scheduled_on,
        due_on=occurrence.due_on,
        status=occurrence.status,
        manually_modified=occurrence.manually_modified,
        series_shift_days=occurrence.series_shift_days,
        preserve_from_series_shift=occurrence.preserve_from_series_shift,
        overdue=(
            occurrence.status in {OccurrenceStatus.PENDING, OccurrenceStatus.POSTPONED}
            and occurrence.due_on < today
        ),
        type=occurrence.type,
        amount=format_money(Decimal(occurrence.amount)),
        description=occurrence.description,
        account_id=occurrence.account_id,
        account_name=names[occurrence.account_id],
        destination_account_id=occurrence.destination_account_id,
        destination_account_name=(
            names[occurrence.destination_account_id]
            if occurrence.destination_account_id is not None
            else None
        ),
        category_id=occurrence.category_id,
        category_name=(
            category_name(session, occurrence.category_id) if occurrence.category_id else None
        ),
        allocate_to_funds=occurrence.allocate_to_funds,
        actual_operation_id=occurrence.actual_operation_id,
        version=occurrence.version,
        created_at=occurrence.created_at,
        updated_at=occurrence.updated_at,
    )


def list_occurrence_responses(
    session: Session,
    *,
    page: int,
    page_size: int,
    due_from: date | None,
    due_to: date | None,
    account_id: UUID | None,
    operation_type: OperationType | None,
    statuses: set[OccurrenceStatus] | None,
    source_kinds: set[OccurrenceSourceKind] | None = None,
    today: date | None = None,
) -> OccurrencePageResponse:
    conditions: list[ColumnElement[bool]] = []
    if due_from is not None:
        conditions.append(ExpectedOccurrence.due_on >= due_from)
    if due_to is not None:
        conditions.append(ExpectedOccurrence.due_on <= due_to)
    if account_id is not None:
        conditions.append(
            or_(
                ExpectedOccurrence.account_id == account_id,
                ExpectedOccurrence.destination_account_id == account_id,
            )
        )
    if operation_type is not None:
        conditions.append(ExpectedOccurrence.type == operation_type)
    if statuses:
        conditions.append(ExpectedOccurrence.status.in_(statuses))
    if source_kinds:
        conditions.append(ExpectedOccurrence.source_kind.in_(source_kinds))
    total = session.scalar(select(func.count()).select_from(ExpectedOccurrence).where(*conditions))
    occurrences = session.scalars(
        select(ExpectedOccurrence)
        .where(*conditions)
        .order_by(ExpectedOccurrence.due_on, ExpectedOccurrence.created_at, ExpectedOccurrence.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    resolved_today = today or _today(session)
    return OccurrencePageResponse(
        items=[
            _occurrence_response(session, occurrence, today=resolved_today)
            for occurrence in occurrences
        ],
        page=page,
        page_size=page_size,
        total=int(total or 0),
    )


def confirm_occurrence(
    session: Session,
    occurrence_id: UUID,
    *,
    expected_version: int,
    amount: Decimal | None = None,
    override: OccurrenceConfirmationOverride | None = None,
    poster: OccurrencePoster,
    occurred_on: date | None = None,
    today: date | None = None,
) -> ExpectedOccurrenceResponse:
    occurrence = _get_occurrence(session, occurrence_id, lock=True)
    if occurrence.status == OccurrenceStatus.CONFIRMED:
        if occurred_on is not None and occurrence.actual_operation_id is not None:
            fact = operation_history_references(session, {occurrence.actual_operation_id})[
                occurrence.actual_operation_id
            ]
            if fact.occurred_on != occurred_on:
                raise SchedulingConflictError
        return _occurrence_response(session, occurrence, today=today or _today(session))
    if occurrence.version != expected_version:
        raise SchedulingConflictError
    if occurrence.status not in {OccurrenceStatus.PENDING, OccurrenceStatus.POSTPONED}:
        raise InvalidOccurrenceTransitionError
    if override is not None:
        _validate_schedule_references(session, override, require_active=True)
    effective_type = override.type if override is not None else occurrence.type
    if override is not None:
        effective_amount = Decimal(override.amount)
    elif amount is not None:
        effective_amount = Decimal(amount)
    else:
        effective_amount = Decimal(occurrence.amount)
    effective_description = override.description if override is not None else occurrence.description
    effective_account_id = override.account_id if override is not None else occurrence.account_id
    effective_destination_account_id = (
        override.destination_account_id
        if override is not None
        else occurrence.destination_account_id
    )
    effective_category_id = override.category_id if override is not None else occurrence.category_id
    effective_allocate_to_funds = (
        override.allocate_to_funds if override is not None else occurrence.allocate_to_funds
    )
    resolved_today = today or _today(session)
    if occurred_on is not None and occurred_on > resolved_today:
        raise FutureOperationDateError
    draft = OccurrenceConfirmationDraft(
        type=effective_type,
        occurred_on=occurred_on
        or (
            resolved_today
            if occurrence.source_kind == OccurrenceSourceKind.ONE_OFF
            or occurrence.due_on > resolved_today
            else occurrence.due_on
        ),
        amount=effective_amount,
        description=effective_description,
        account_id=effective_account_id,
        destination_account_id=effective_destination_account_id,
        category_id=effective_category_id,
        allocate_to_funds=effective_allocate_to_funds,
    )
    operation_id = poster(draft)
    snapshot_changed = any(
        (
            occurrence.type != effective_type,
            Decimal(occurrence.amount) != effective_amount,
            occurrence.description != effective_description,
            occurrence.account_id != effective_account_id,
            occurrence.destination_account_id != effective_destination_account_id,
            occurrence.category_id != effective_category_id,
            occurrence.allocate_to_funds != effective_allocate_to_funds,
        )
    )
    if snapshot_changed:
        occurrence.type = effective_type
        occurrence.amount = effective_amount
        occurrence.description = effective_description
        occurrence.account_id = effective_account_id
        occurrence.destination_account_id = effective_destination_account_id
        occurrence.category_id = effective_category_id
        occurrence.allocate_to_funds = effective_allocate_to_funds
        occurrence.manually_modified = True
    _link_confirmed_operation(occurrence, operation_id)
    session.flush()
    return _occurrence_response(session, occurrence, today=resolved_today)


def _link_confirmed_operation(occurrence: ExpectedOccurrence, operation_id: UUID) -> None:
    occurrence.status = OccurrenceStatus.CONFIRMED
    occurrence.actual_operation_id = operation_id
    occurrence.version += 1
    occurrence.updated_at = datetime.now(UTC)


def postpone_occurrence(
    session: Session,
    occurrence_id: UUID,
    *,
    due_on: date,
    expected_version: int,
    expected_rule_version: int | None = None,
    today: date | None = None,
) -> OccurrencePostponeResponse:
    source_kind, rule_id = session.execute(
        select(ExpectedOccurrence.source_kind, ExpectedOccurrence.rule_id).where(
            ExpectedOccurrence.id == occurrence_id
        )
    ).one_or_none() or (None, None)
    if source_kind == OccurrenceSourceKind.ONE_OFF:
        occurrence = _get_occurrence(session, occurrence_id, lock=True)
        if occurrence.version != expected_version:
            raise SchedulingConflictError
        if (
            occurrence.status not in {OccurrenceStatus.PENDING, OccurrenceStatus.POSTPONED}
            or occurrence.due_on == due_on
        ):
            raise InvalidOccurrenceTransitionError
        occurrence.scheduled_on = due_on
        occurrence.due_on = due_on
        occurrence.status = OccurrenceStatus.PENDING
        occurrence.manually_modified = False
        occurrence.version += 1
        occurrence.updated_at = datetime.now(UTC)
        session.flush()
        response = _occurrence_response(session, occurrence, today=today or _today(session))
        return OccurrencePostponeResponse(
            **response.model_dump(),
            series_shift_applied=False,
            shift_days=0,
            shifted_occurrences=0,
            preserved_occurrences=0,
            rule_version=0,
        )
    if rule_id is None:
        raise ExpectedOccurrenceNotFoundError
    rule = _get_rule(session, rule_id, lock=True)
    if rule.shift_future_on_postpone and (
        expected_rule_version is None or rule.version != expected_rule_version
    ):
        raise SchedulingConflictError
    occurrence = _get_occurrence(session, occurrence_id, lock=True)
    if occurrence.rule_id != rule.id:
        raise ExpectedOccurrenceNotFoundError
    if occurrence.version != expected_version:
        raise SchedulingConflictError
    if (
        occurrence.status not in {OccurrenceStatus.PENDING, OccurrenceStatus.POSTPONED}
        or occurrence.due_on == due_on
    ):
        raise InvalidOccurrenceTransitionError
    shift_days = (due_on - occurrence.due_on).days
    occurrence.due_on = due_on
    occurrence.status = OccurrenceStatus.POSTPONED
    occurrence.manually_modified = True
    occurrence.series_shift_days += shift_days
    occurrence.version += 1
    now = datetime.now(UTC)
    occurrence.updated_at = now
    shifted_occurrences = 0
    preserved_occurrences = 0
    if rule.shift_future_on_postpone:
        siblings = _lock_series_shift_candidates(
            session,
            rule.id,
            after_scheduled_on=occurrence.scheduled_on,
        )
        future_occurrence_count = int(
            session.scalar(
                select(func.count())
                .select_from(ExpectedOccurrence)
                .where(
                    ExpectedOccurrence.rule_id == rule.id,
                    ExpectedOccurrence.scheduled_on > occurrence.scheduled_on,
                )
            )
            or 0
        )
        rule.series_shift_days += shift_days
        rule.version += 1
        rule.updated_at = now
        for sibling in siblings:
            if sibling.status == OccurrenceStatus.CANCELLED:
                sibling.preserve_from_series_shift = True
                sibling.version += 1
                sibling.updated_at = now
                continue
            sibling.series_shift_days += shift_days
            sibling.due_on = _shift_date(sibling.due_on, shift_days)
            sibling.version += 1
            sibling.updated_at = now
            shifted_occurrences += 1
        preserved_occurrences = future_occurrence_count - shifted_occurrences
        resolved_today = today or _today(session)
        _materialize_missing_occurrences(
            session,
            rule,
            horizon_from=resolved_today,
            horizon_to=calendar_year_later(resolved_today),
            now=now,
        )
    session.flush()
    response = _occurrence_response(session, occurrence, today=today or _today(session))
    return OccurrencePostponeResponse(
        **response.model_dump(),
        series_shift_applied=rule.shift_future_on_postpone,
        shift_days=shift_days,
        shifted_occurrences=shifted_occurrences,
        preserved_occurrences=preserved_occurrences,
        rule_version=rule.version,
    )


def cancel_occurrence(
    session: Session, occurrence_id: UUID, *, expected_version: int, today: date | None = None
) -> ExpectedOccurrenceResponse:
    occurrence = _get_occurrence(session, occurrence_id, lock=True)
    resolved_today = today or _today(session)
    if occurrence.status == OccurrenceStatus.CANCELLED and occurrence.manually_modified:
        return _occurrence_response(session, occurrence, today=resolved_today)
    if occurrence.version != expected_version:
        raise SchedulingConflictError
    if occurrence.status not in {OccurrenceStatus.PENDING, OccurrenceStatus.POSTPONED}:
        raise InvalidOccurrenceTransitionError
    occurrence.status = OccurrenceStatus.CANCELLED
    occurrence.due_on = _shift_date(occurrence.scheduled_on, occurrence.series_shift_days)
    occurrence.manually_modified = True
    occurrence.version += 1
    occurrence.updated_at = datetime.now(UTC)
    session.flush()
    return _occurrence_response(session, occurrence, today=resolved_today)
