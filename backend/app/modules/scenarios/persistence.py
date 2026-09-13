"""Scenario metadata only. Saving never calls a financial command."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.modules.scenarios.models import SavedScenario
from app.modules.scenarios.service import ScenarioError
from app.modules.scenarios.workspace_schemas import SavedWorkspace, SaveWorkspace


def response(row: SavedScenario) -> SavedWorkspace:
    return SavedWorkspace.model_validate(
        {key: getattr(row, key) for key in SavedWorkspace.model_fields}
    )


def list_saved(session: Session) -> list[SavedWorkspace]:
    return [
        response(row)
        for row in session.scalars(
            select(SavedScenario).order_by(SavedScenario.updated_at.desc(), SavedScenario.id)
        ).all()
    ]


def save(session: Session, payload: SaveWorkspace, identity: UUID | None = None) -> SavedWorkspace:
    now = datetime.now(UTC)
    row: SavedScenario | None
    if identity is None:
        if payload.version is not None:
            raise ScenarioError("scenario_saved_conflict", 409)
        session.execute(text("SELECT pg_advisory_xact_lock(hashtext('hermes.saved_scenarios'))"))
        if (session.scalar(select(func.count()).select_from(SavedScenario)) or 0) >= 100:
            raise ScenarioError("scenario_saved_limit")
        row = SavedScenario(
            name=payload.name,
            workspace=payload.workspace.model_dump(mode="json"),
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row = session.scalar(
            select(SavedScenario).where(SavedScenario.id == identity).with_for_update()
        )
        if row is None:
            raise ScenarioError("scenario_saved_missing", 404)
        if row.version != payload.version:
            raise ScenarioError("scenario_saved_conflict", 409)
        row.name = payload.name
        row.workspace = payload.workspace.model_dump(mode="json")
        row.version += 1
        row.updated_at = now
    session.flush()
    return response(row)


def remove(session: Session, identity: UUID, version: int) -> None:
    row = session.scalar(
        select(SavedScenario).where(SavedScenario.id == identity).with_for_update()
    )
    if row is None:
        raise ScenarioError("scenario_saved_missing", 404)
    if row.version != version:
        raise ScenarioError("scenario_saved_conflict", 409)
    session.delete(row)
