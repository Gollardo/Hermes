"""Public provenance persistence for application-owned workflows."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.imports.errors import ImportDecisionError, ImportGroupingError
from app.modules.imports.grouping import decision_groups
from app.modules.imports.models import ImportReceipt
from app.modules.imports.parser import normalize, parse_source_date, read_file
from app.modules.imports.schemas import CommitRequest, PreviewRequest


@dataclass(frozen=True)
class ImportProvenance:
    source_date: date | None
    source_description: str | None


def find_receipt(session: Session, key: str) -> ImportReceipt | None:
    return session.scalar(select(ImportReceipt).where(ImportReceipt.source_key == key))


def record_receipt(
    session: Session,
    key: str,
    decision_hash: str,
    operation_id: UUID,
    *,
    source_date: date | None,
    source_description: str | None,
) -> None:
    session.add(
        ImportReceipt(
            source_key=key,
            decision_hash=decision_hash,
            operation_id=operation_id,
            source_date=source_date,
            source_description=source_description,
        )
    )


def operation_provenance(session: Session, operation_id: UUID) -> list[ImportProvenance]:
    receipts = session.scalars(
        select(ImportReceipt)
        .where(ImportReceipt.operation_id == operation_id)
        .order_by(ImportReceipt.id)
    )
    return [
        ImportProvenance(
            source_date=receipt.source_date,
            source_description=receipt.source_description,
        )
        for receipt in receipts
    ]


def receipt_ids(session: Session, keys: list[str]) -> dict[str, UUID]:
    return {
        r.source_key: r.operation_id
        for r in session.scalars(select(ImportReceipt).where(ImportReceipt.source_key.in_(keys)))
    }


__all__ = [
    "CommitRequest",
    "ImportGroupingError",
    "decision_groups",
    "PreviewRequest",
    "ImportDecisionError",
    "normalize",
    "parse_source_date",
    "read_file",
    "find_receipt",
    "ImportProvenance",
    "operation_provenance",
    "record_receipt",
    "receipt_ids",
]
