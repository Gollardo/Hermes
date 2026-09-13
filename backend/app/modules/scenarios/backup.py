"""Only Backup may use this module-owned persistence surface."""

from app.modules.scenarios.models import SavedScenario

__all__ = ["SavedScenario", "validate_saved_workspace"]


def validate_saved_workspace(payload: dict[str, object]) -> None:
    from app.modules.scenarios.workspace_schemas import Workspace

    Workspace.model_validate(payload)
