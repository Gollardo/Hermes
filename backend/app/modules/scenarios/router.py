from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from app.core.database import DatabaseSession, ProjectionSession
from app.modules.scenarios import persistence
from app.modules.scenarios.schemas import ScenarioComparison, ScenarioContext, ScenarioRequest
from app.modules.scenarios.service import ScenarioError, compare
from app.modules.scenarios.snapshot import context, load_snapshot
from app.modules.scenarios.workspace_engine import compare_workspace, solve_workspace
from app.modules.scenarios.workspace_schemas import (
    SavedWorkspace,
    SaveWorkspace,
    SolveRequest,
    SolveResult,
    Workspace,
    WorkspaceResult,
)
from app.modules.scenarios.workspace_snapshot import load_workspace_snapshot, workspace_context

read_router = APIRouter(prefix="/scenarios", tags=["scenarios"])
write_router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@read_router.get("/context", response_model=ScenarioContext)
def read_context(session: ProjectionSession) -> ScenarioContext:
    return context(load_snapshot(session))


@write_router.post("/compare", response_model=ScenarioComparison)
def compare_scenario(payload: ScenarioRequest, session: ProjectionSession) -> ScenarioComparison:
    try:
        return compare(load_snapshot(session), payload)
    except ScenarioError as error:
        raise HTTPException(status_code=error.status, detail={"code": error.code}) from error


@read_router.get("/workspace-context")
def read_workspace_context(session: ProjectionSession) -> dict[str, object]:
    try:
        return workspace_context(load_workspace_snapshot(session))
    except ScenarioError as error:
        raise HTTPException(status_code=error.status, detail={"code": error.code}) from error


@write_router.post("/workspaces/compare", response_model=WorkspaceResult)
def compare_program(payload: Workspace, session: ProjectionSession) -> WorkspaceResult:
    try:
        return compare_workspace(load_workspace_snapshot(session), payload)
    except ScenarioError as error:
        raise HTTPException(status_code=error.status, detail={"code": error.code}) from error


@write_router.post("/workspaces/solve", response_model=SolveResult)
def solve_program(payload: SolveRequest, session: ProjectionSession) -> SolveResult:
    try:
        return solve_workspace(load_workspace_snapshot(session), payload)
    except ScenarioError as error:
        raise HTTPException(status_code=error.status, detail={"code": error.code}) from error


@read_router.get("/saved", response_model=list[SavedWorkspace], response_model_exclude_none=True)
def read_saved(session: DatabaseSession) -> list[SavedWorkspace]:
    return persistence.list_saved(session)


@write_router.post(
    "/saved", response_model=SavedWorkspace, status_code=201, response_model_exclude_none=True
)
def create_saved(payload: SaveWorkspace, session: DatabaseSession) -> SavedWorkspace:
    try:
        return persistence.save(session, payload)
    except ScenarioError as error:
        raise HTTPException(status_code=error.status, detail={"code": error.code}) from error


@write_router.put(
    "/saved/{scenario_id}", response_model=SavedWorkspace, response_model_exclude_none=True
)
def update_saved(
    scenario_id: UUID, payload: SaveWorkspace, session: DatabaseSession
) -> SavedWorkspace:
    try:
        return persistence.save(session, payload, scenario_id)
    except ScenarioError as error:
        raise HTTPException(status_code=error.status, detail={"code": error.code}) from error


@write_router.delete("/saved/{scenario_id}", status_code=204)
def delete_saved(
    scenario_id: UUID, session: DatabaseSession, version: int = Query(ge=1)
) -> Response:
    try:
        persistence.remove(session, scenario_id, version)
        return Response(status_code=204)
    except ScenarioError as error:
        raise HTTPException(status_code=error.status, detail={"code": error.code}) from error
