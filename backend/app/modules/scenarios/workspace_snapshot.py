"""Read financial owners once. No calendar synchronization or financial writes."""

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.categories.contracts import ProjectionCategory, projection_categories
from app.modules.forecasting.contracts import ProjectionSnapshot
from app.modules.funds.contracts import funded_expense_ids, projection_positions, reserve_balances
from app.modules.operations.contracts import ExpenseFact, expense_history
from app.modules.scenarios.service import ScenarioError
from app.modules.scenarios.snapshot import context, fingerprint, load_snapshot
from app.modules.scheduling.contracts import projection_schedule


def month_shift(value: date, count: int) -> date:
    index = value.year * 12 + value.month - 1 + count
    return date(index // 12, index % 12 + 1, 1)


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    projection: ProjectionSnapshot
    categories: tuple[ProjectionCategory, ...]
    history: tuple[ExpenseFact, ...]
    funded_operations: frozenset[UUID]


def identity(source: WorkspaceSnapshot) -> str:
    payload = {
        "projection": fingerprint(source.projection),
        "categories": [asdict(c) for c in source.categories],
        "history": [asdict(f) for f in source.history],
        "funded_operations": sorted(source.funded_operations),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def load_workspace_snapshot(session: Session) -> WorkspaceSnapshot:
    projection = load_snapshot(session)
    schedule = projection_schedule(
        session, today=projection.today, through_on=projection.through_on
    )
    if len(schedule.occurrences) > 5000:
        raise ScenarioError("scenario_event_limit")
    projection = replace(
        projection,
        occurrences=tuple(schedule.occurrences),
        fund_positions=projection_positions(session),
        reserve_by_account=tuple(sorted(reserve_balances(session).items())),
    )
    try:
        history = expense_history(
            session,
            from_on=month_shift(projection.today, -6),
            through_on=projection.today,
        )
    except ValueError as error:
        raise ScenarioError("scenario_history_limit") from error
    return WorkspaceSnapshot(
        projection, projection_categories(session), history, funded_expense_ids(session)
    )


def workspace_context(source: WorkspaceSnapshot) -> dict[str, object]:
    result = context(source.projection).model_dump(mode="json")
    result.update(
        snapshot_id=identity(source),
        source_policy="complete_read_only_schedule",
        categories=[asdict(c) for c in source.categories],
        funds=[{"id": f.id, "name": f.name} for f in source.projection.funds],
        plans=[
            {**p, "category_id": e.category_id, "rule_id": e.rule_id, "origin": e.origin}
            for p, e in zip(result["plans"], source.projection.occurrences, strict=True)
        ],
        history_from=month_shift(source.projection.today, -6),
        history_through=source.projection.today,
        history=[
            {**asdict(f), "amount": str(f.amount)}
            for f in source.history
            if f.id not in source.funded_operations
        ],
    )
    return result
