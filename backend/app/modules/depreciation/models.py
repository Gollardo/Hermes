from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DepreciationPurchase(Base):
    __tablename__ = "depreciation_purchases"
    __table_args__ = (
        CheckConstraint("cost > 0", name="ck_depreciation_cost"),
        CheckConstraint("months BETWEEN 1 AND 600", name="ck_depreciation_months"),
        CheckConstraint("inflation BETWEEN 0 AND 100", name="ck_depreciation_inflation"),
        CheckConstraint("version > 0", name="ck_depreciation_version"),
    )
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    fund_id: Mapped[UUID] = mapped_column(ForeignKey("funds.id", ondelete="RESTRICT"), unique=True)
    cost: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    purchase_month: Mapped[str] = mapped_column(String(7))
    months: Mapped[int]
    inflation: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DepreciationReceipt(Base):
    __tablename__ = "depreciation_receipts"
    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    purchase_id: Mapped[UUID] = mapped_column(
        ForeignKey("depreciation_purchases.id", ondelete="RESTRICT"), index=True
    )
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("fund_events.id", ondelete="RESTRICT"), unique=True
    )
    fingerprint: Mapped[str] = mapped_column(String(64))
