from fastapi import APIRouter, HTTPException

from app.core.database import ProjectionSession
from app.modules.scenarios.schemas import ScenarioComparison, ScenarioContext, ScenarioRequest
from app.modules.scenarios.service import ScenarioError, compare
from app.modules.scenarios.snapshot import context, load_snapshot

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
