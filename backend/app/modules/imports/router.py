from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from app.application.imports import commit, preview
from app.core.database import DatabaseSession
from app.modules.imports.errors import ImportDecisionError
from app.modules.imports.models import ImportProfile
from app.modules.imports.parser import read_file
from app.modules.imports.schemas import (
    CommitRequest,
    FileRequest,
    Mapping,
    PreviewRequest,
    ProfileRequest,
)


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


read_router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[Depends(no_store)])
write_router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[Depends(no_store)])


def failure(error: Exception) -> HTTPException:
    row = error.row if isinstance(error, ImportDecisionError) else None
    error = error.cause if isinstance(error, ImportDecisionError) else error
    domain_codes = {
        "InsufficientBalanceError": "insufficient_balance",
        "FundCoverageError": "insufficient_free_balance",
        "FundBalanceError": "insufficient_fund_balance",
        "FutureOperationDateError": "future_operation_requires_plan",
        "AccountReferenceError": "invalid_account_reference",
        "CategoryReferenceError": "invalid_category_reference",
        "FundNotFoundError": "invalid_fund_reference",
    }
    message = str(error)
    code = domain_codes.get(type(error).__name__, "import_invalid")
    if "currency" in message:
        code = "import_currency"
    elif "changed" in message or "already" in message:
        code = "import_conflict"
    elif "match" in message or "preserve" in message:
        code = "import_mismatch"
    elif "Too many" in message or "exceeds" in message:
        code = "import_limit"
    return HTTPException(
        409 if isinstance(error, RuntimeError) else 422, detail={"code": code, "row": row}
    )


@write_router.post("/inspect")
def inspect_file(payload: FileRequest) -> dict[str, Any]:
    try:
        _, sheets, rows = read_file(payload)
        return dict(sheets=sheets, rows=rows)
    except ValueError as error:
        raise failure(error) from error


@write_router.post("/preview")
def preview_file(payload: PreviewRequest, session: DatabaseSession) -> dict[str, Any]:
    try:
        return preview(session, payload)
    except (ValueError, RuntimeError, OverflowError, ImportDecisionError) as error:
        raise failure(error) from error


@write_router.post("/commit")
def commit_file(payload: CommitRequest, session: DatabaseSession) -> dict[str, Any]:
    try:
        return commit(session, payload)
    except (ValueError, RuntimeError, OverflowError, ImportDecisionError) as error:
        raise failure(error) from error


@read_router.get("/profiles")
def profiles(session: DatabaseSession) -> list[dict[str, Any]]:
    saved = [
        dict(name=p.name, mapping=p.mapping)
        for p in session.scalars(select(ImportProfile).order_by(ImportProfile.name))
    ]
    return (
        saved
        if any(p["name"] == "XLSX" for p in saved)
        else [dict(name="XLSX", mapping=Mapping().model_dump())] + saved
    )


@write_router.put("/profiles")
def save_profile(payload: ProfileRequest, session: DatabaseSession) -> dict[str, bool]:
    from sqlalchemy.dialects.postgresql import insert

    statement = insert(ImportProfile).values(
        name=payload.name.strip(), mapping=payload.mapping.model_dump()
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[ImportProfile.name], set_={"mapping": payload.mapping.model_dump()}
        )
    )
    return {"saved": True}
