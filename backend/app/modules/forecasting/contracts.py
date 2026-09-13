"""Public exact projection contract for read-side consumers."""

from app.modules.forecasting.program import ProgramResult, project_program
from app.modules.forecasting.projection import (
    ProjectionResult,
    ProjectionSnapshot,
    project_snapshot,
)
from app.modules.forecasting.schemas import ForecastHorizon, ForecastResponse
from app.modules.forecasting.service import horizon_end

__all__ = [
    "ProjectionResult",
    "ProjectionSnapshot",
    "project_snapshot",
    "ForecastHorizon",
    "ForecastResponse",
    "horizon_end",
]


__all__ += ["ProgramResult", "project_program"]
