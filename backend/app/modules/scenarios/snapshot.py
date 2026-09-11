"""Load public source contracts once, within ProjectionSession's read-only MVCC snapshot."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.modules.accounts.contracts import list_account_identities
from app.modules.forecasting.contracts import ForecastHorizon, ProjectionSnapshot, horizon_end
from app.modules.funds.contracts import projection_funds, reserve_balances, reserved_balances
from app.modules.operations.contracts import account_balances
from app.modules.scenarios.schemas import AccountChoice, PlanChoice, ScenarioContext
from app.modules.scheduling.contracts import forecast_schedule_snapshot
from app.modules.settings.contracts import get_application_settings


def load_snapshot(session: Session) -> ProjectionSnapshot:
    settings = get_application_settings(session)
    today = datetime.now(UTC).astimezone(ZoneInfo(settings.timezone)).date()
    through = horizon_end(today, ForecastHorizon.YEAR)
    schedule = forecast_schedule_snapshot(
        session, today=today, due_to=through, account_id=None, shared_lock=False
    )
    accounts = tuple(list_account_identities(session))
    ids = {item.id for item in accounts}
    return ProjectionSnapshot(
        today=today,
        through_on=through,
        currency=settings.base_currency,
        accounts=accounts,
        balances=tuple(sorted(account_balances(session, ids).items())),
        reserved=tuple(sorted(reserved_balances(session, ids).items())),
        funds=tuple(projection_funds(session)),
        mode=settings.fund_allocation_mode,
        occurrences=tuple(schedule.occurrences),
        overdue_count=schedule.overdue_count,
        overdue_by_account=tuple(sorted(schedule.overdue_count_by_account.items())),
        reserve_total=sum(reserve_balances(session).values(), Decimal(0)),
    )


def fingerprint(snapshot: ProjectionSnapshot) -> str:
    payload = asdict(snapshot)
    payload["funds"] = [item.model_dump(mode="json") for item in snapshot.funds]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def context(snapshot: ProjectionSnapshot) -> ScenarioContext:
    names = {item.id: item.name for item in snapshot.accounts}
    return ScenarioContext(
        snapshot_id=fingerprint(snapshot),
        today=snapshot.today,
        maximum_on=snapshot.through_on,
        currency=snapshot.currency,
        accounts=[
            AccountChoice(id=item.id, name=item.name, archived=item.archived)
            for item in snapshot.accounts
        ],
        overdue_excluded_count=snapshot.overdue_count,
        plans=[
            PlanChoice(
                id=item.id,
                version=item.version,
                due_on=item.due_on,
                amount=format(item.amount, "f"),
                type=item.type.value,
                description=item.description,
                account_id=item.account_id,
                account_name=names[item.account_id],
                destination_account_id=item.destination_account_id,
                destination_account_name=names[item.destination_account_id]
                if item.destination_account_id
                else None,
                allocate_to_funds=item.allocate_to_funds,
            )
            for item in snapshot.occurrences
        ],
    )
