from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import JSON, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ImportProfile(Base):
    __tablename__ = "import_profiles"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    mapping: Mapped[dict[str, object]] = mapped_column(JSON)


class ImportReceipt(Base):
    __tablename__ = "import_receipts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_key: Mapped[str] = mapped_column(String(64), unique=True)
    decision_hash: Mapped[str] = mapped_column(String(64))
    operation_id: Mapped[UUID] = mapped_column()
    source_date: Mapped[date | None] = mapped_column(Date)
    source_description: Mapped[str | None] = mapped_column(String(4000))
    # Deliberately retained after operation deletion; this is provenance, not a ledger FK.
