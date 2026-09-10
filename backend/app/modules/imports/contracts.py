"""Public provenance persistence for the application import transaction."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.imports.errors import ImportDecisionError
from app.modules.imports.models import ImportReceipt
from app.modules.imports.parser import normalize, read_file
from app.modules.imports.schemas import CommitRequest, PreviewRequest


def find_receipt(session: Session, key: str) -> ImportReceipt | None:
    return session.scalar(select(ImportReceipt).where(ImportReceipt.source_key == key))


def record_receipt(session: Session, key: str, decision_hash: str, operation_id: UUID) -> None:
    session.add(
        ImportReceipt(source_key=key, decision_hash=decision_hash, operation_id=operation_id)
    )


def receipt_ids(session: Session, keys: list[str]) -> dict[str, UUID]:
    return {
        r.source_key: r.operation_id
        for r in session.scalars(select(ImportReceipt).where(ImportReceipt.source_key.in_(keys)))
    }


__all__ = [
    "CommitRequest",
    "PreviewRequest",
    "ImportDecisionError",
    "normalize",
    "read_file",
    "find_receipt",
    "record_receipt",
    "receipt_ids",
]
