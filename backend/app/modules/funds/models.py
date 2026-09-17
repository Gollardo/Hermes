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
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FundEventType(StrEnum):
    ALLOCATION = "allocation"
    REDISTRIBUTION = "redistribution"
    FUND_TRANSFER = "fund_transfer"
    RESERVE_DISTRIBUTION = "reserve_distribution"
    RESERVE_RELEASE = "reserve_release"
    FUND_RELEASE = "fund_release"


class Fund(Base):
    __tablename__ = "funds"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_funds_name_not_blank"),
        CheckConstraint(
            "allocation_percentage >= 0 AND allocation_percentage <= 100",
            name="ck_funds_allocation_percentage_range",
        ),
        CheckConstraint(
            "target_amount IS NULL OR target_amount > 0",
            name="ck_funds_target_amount_positive",
        ),
        CheckConstraint("version > 0", name="ck_funds_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    managed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    allocation_percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    target_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(default=1)


class FundEvent(Base):
    __tablename__ = "fund_events"
    __table_args__ = (Index("ix_fund_events_history_order", "occurred_on", "created_at", "id"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    type: Mapped[FundEventType] = mapped_column(
        Enum(
            FundEventType,
            name="fund_event_type",
            values_callable=lambda values: [value.value for value in values],
        )
    )
    occurred_on: Mapped[date]
    description: Mapped[str | None] = mapped_column(Text)
    caused_by_operation_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("financial_operations.id", ondelete="CASCADE"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FundMovement(Base):
    __tablename__ = "fund_movements"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_fund_movements_amount_nonzero"),
        CheckConstraint(
            "(operation_id IS NOT NULL)::int + (event_id IS NOT NULL)::int = 1",
            name="ck_fund_movements_one_source",
        ),
        UniqueConstraint(
            "operation_id",
            "fund_id",
            "account_id",
            name="uq_fund_movements_operation_position",
        ),
        UniqueConstraint(
            "event_id", "fund_id", "account_id", name="uq_fund_movements_event_position"
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    fund_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("funds.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    operation_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("financial_operations.id", ondelete="CASCADE"),
        index=True,
    )
    event_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("fund_events.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)


class FundReserveMovement(Base):
    __tablename__ = "fund_reserve_movements"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_fund_reserve_movements_amount_nonzero"),
        UniqueConstraint("event_id", "account_id", name="uq_fund_reserve_movements_event_position"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    event_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("fund_events.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
