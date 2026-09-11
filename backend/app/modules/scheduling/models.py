from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.operations.contracts import OperationType


class RecurrenceFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class OccurrenceStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class OccurrenceSourceKind(StrEnum):
    RECURRING = "recurring"
    ONE_OFF = "one_off"


def _operation_type_column() -> Enum:
    return Enum(
        OperationType,
        name="financial_operation_type",
        values_callable=lambda values: [value.value for value in values],
    )


class RecurringRule(Base):
    __tablename__ = "recurring_rules"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_recurring_rules_amount_positive"),
        CheckConstraint("version > 0", name="ck_recurring_rules_version_positive"),
        CheckConstraint("interval BETWEEN 1 AND 3", name="ck_recurring_rules_interval"),
        CheckConstraint(
            "frequency IN ('weekly', 'monthly') OR interval = 1",
            name="ck_recurring_rules_interval_frequency",
        ),
        CheckConstraint(
            "(frequency = 'weekly' AND weekdays IS NOT NULL "
            "AND cardinality(weekdays) BETWEEN 1 AND 7 "
            "AND weekdays <@ ARRAY[1,2,3,4,5,6,7]::smallint[]) OR "
            "(frequency <> 'weekly' AND weekdays IS NULL)",
            name="ck_recurring_rules_weekdays",
        ),
        CheckConstraint(
            "weekdays IS NULL OR cardinality(weekdays) = "
            "(CASE WHEN 1 = ANY(weekdays) THEN 1 ELSE 0 END + "
            "CASE WHEN 2 = ANY(weekdays) THEN 1 ELSE 0 END + "
            "CASE WHEN 3 = ANY(weekdays) THEN 1 ELSE 0 END + "
            "CASE WHEN 4 = ANY(weekdays) THEN 1 ELSE 0 END + "
            "CASE WHEN 5 = ANY(weekdays) THEN 1 ELSE 0 END + "
            "CASE WHEN 6 = ANY(weekdays) THEN 1 ELSE 0 END + "
            "CASE WHEN 7 = ANY(weekdays) THEN 1 ELSE 0 END)",
            name="ck_recurring_rules_weekdays_unique",
        ),
        CheckConstraint("end_on IS NULL OR end_on >= start_on", name="ck_recurring_rules_dates"),
        CheckConstraint(
            "frequency <> 'monthly' OR extract(day from start_on) <= 28",
            name="ck_recurring_rules_monthly_day",
        ),
        CheckConstraint(
            "frequency <> 'yearly' OR extract(month from start_on) <> 2 "
            "OR extract(day from start_on) <> 29",
            name="ck_recurring_rules_yearly_day",
        ),
        CheckConstraint(
            "(type IN ('income', 'expense') AND category_id IS NOT NULL "
            "AND destination_account_id IS NULL) OR "
            "(type = 'transfer' AND category_id IS NULL "
            "AND destination_account_id IS NOT NULL "
            "AND destination_account_id <> account_id)",
            name="ck_recurring_rules_operation_shape",
        ),
        CheckConstraint(
            "NOT allocate_to_funds OR type = 'transfer'",
            name="ck_recurring_rules_fund_allocation_transfer",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    type: Mapped[OperationType] = mapped_column(_operation_type_column())
    frequency: Mapped[RecurrenceFrequency] = mapped_column(
        Enum(
            RecurrenceFrequency,
            name="recurrence_frequency",
            values_callable=lambda values: [value.value for value in values],
        )
    )
    interval: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    weekdays: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger))
    start_on: Mapped[date]
    end_on: Mapped[date | None]
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    destination_account_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    allocate_to_funds: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shift_future_on_postpone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    series_shift_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExpectedOccurrence(Base):
    __tablename__ = "expected_occurrences"
    __table_args__ = (
        Index(
            "ix_occurrences_oracle_due",
            "due_on",
            "id",
            postgresql_where=text("status IN ('pending', 'postponed')"),
        ),
        CheckConstraint("amount > 0", name="ck_expected_occurrences_amount_positive"),
        CheckConstraint("version > 0", name="ck_expected_occurrences_version_positive"),
        CheckConstraint(
            "(type IN ('income', 'expense') AND category_id IS NOT NULL "
            "AND destination_account_id IS NULL) OR "
            "(type = 'transfer' AND category_id IS NULL "
            "AND destination_account_id IS NOT NULL "
            "AND destination_account_id <> account_id)",
            name="ck_expected_occurrences_operation_shape",
        ),
        CheckConstraint(
            "NOT allocate_to_funds OR type = 'transfer'",
            name="ck_expected_occurrences_fund_allocation_transfer",
        ),
        CheckConstraint(
            "(status = 'confirmed' AND actual_operation_id IS NOT NULL) OR "
            "(status <> 'confirmed' AND actual_operation_id IS NULL)",
            name="ck_expected_occurrences_confirmation_link",
        ),
        CheckConstraint(
            "source_kind = 'one_off' OR status <> 'postponed' OR manually_modified",
            name="ck_expected_occurrences_postponed_manual",
        ),
        CheckConstraint(
            "source_kind = 'one_off' OR NOT (status = 'pending' AND manually_modified)",
            name="ck_expected_occurrences_pending_automatic",
        ),
        CheckConstraint(
            "source_kind = 'one_off' OR status IN ('postponed', 'confirmed') "
            "OR due_on = scheduled_on + series_shift_days",
            name="ck_expected_occurrences_due_date",
        ),
        CheckConstraint(
            "source_kind = 'one_off' OR NOT preserve_from_series_shift "
            "OR (status = 'cancelled' AND NOT manually_modified)",
            name="ck_expected_occurrences_series_shift_preservation",
        ),
        CheckConstraint(
            "(source_kind = 'recurring' AND rule_id IS NOT NULL) OR "
            "(source_kind = 'one_off' AND rule_id IS NULL)",
            name="ck_expected_occurrences_source_rule",
        ),
        Index("ix_expected_occurrences_calendar", "due_on", "status", "id"),
        Index(
            "uq_expected_occurrences_recurring_rule_date",
            "rule_id",
            "scheduled_on",
            unique=True,
            postgresql_where=text("source_kind = 'recurring'"),
        ),
        Index(
            "ix_expected_occurrences_series_shift_candidates",
            "rule_id",
            "scheduled_on",
            "id",
            postgresql_where=text(
                "status = 'pending' OR "
                "(status = 'cancelled' AND NOT manually_modified "
                "AND NOT preserve_from_series_shift)"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_kind: Mapped[OccurrenceSourceKind] = mapped_column(
        Enum(
            OccurrenceSourceKind,
            name="expected_occurrence_source_kind",
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=OccurrenceSourceKind.RECURRING,
    )
    rule_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("recurring_rules.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    scheduled_on: Mapped[date]
    due_on: Mapped[date]
    status: Mapped[OccurrenceStatus] = mapped_column(
        Enum(
            OccurrenceStatus,
            name="expected_occurrence_status",
            values_callable=lambda values: [value.value for value in values],
        )
    )
    manually_modified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    series_shift_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preserve_from_series_shift: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    type: Mapped[OperationType] = mapped_column(_operation_type_column())
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    destination_account_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    allocate_to_funds: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actual_operation_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "financial_operations.id",
            ondelete="RESTRICT",
            name="fk_expected_occurrences_actual_operation",
        ),
        unique=True,
    )
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
