from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.modules.backup.schemas import BackupDocument
from app.modules.backup.service import create_backup, restore_backup, seal_backup
from app.modules.scenarios.models import SavedScenario
from app.modules.scenarios.workspace_snapshot import month_shift
from app.modules.scheduling.models import ExpectedOccurrence, OccurrenceStatus


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": str(client.cookies.get("XSRF-TOKEN"))}


def initialize(client: TestClient) -> tuple[str, str, str]:
    assert (
        client.post(
            "/api/v1/setup",
            json={
                "master_password": "workspace-test-password",
                "base_currency": "RUB",
                "timezone": "Europe/Moscow",
            },
        ).status_code
        == 201
    )
    account = client.post(
        "/api/v1/accounts",
        headers=csrf(client),
        json={"name": "Main", "type": "debit", "initial_balance": "100000.0001"},
    ).json()["id"]
    category = client.post(
        "/api/v1/categories", headers=csrf(client), json={"name": "Living", "type": "expense"}
    ).json()["id"]
    today = client.get("/api/v1/settings").json()["application_today"]
    return account, category, today


def draft(context: dict[str, Any], account: str, today: str) -> dict[str, Any]:
    return {
        "snapshot_id": context["snapshot_id"],
        "stop_loss": "20000.0001",
        "variants": [
            {
                "id": str(uuid4()),
                "name": "Purchase and move",
                "decisions": [
                    {
                        "id": str(uuid4()),
                        "action": "expense",
                        "account_id": account,
                        "amount": "10000.0001",
                        "due_on": today,
                    },
                    {
                        "id": str(uuid4()),
                        "action": "expense",
                        "account_id": account,
                        "amount": "20000.0001",
                        "due_on": today,
                    },
                ],
            }
        ],
    }


def financial_state(session: Session) -> dict[str, list[str]]:
    return {
        name: sorted(session.scalars(text(f'SELECT row_to_json(t)::text FROM "{name}" t')).all())
        for name in inspect(session.get_bind()).get_table_names()
        if name not in {"auth_sessions", "login_throttle", "owner_credentials", "saved_scenarios"}
    }


def test_workspace_api_calculation_errors_and_solver_never_write_financial_state(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        account, category, today = initialize(client)
        context = client.get("/api/v1/scenarios/workspace-context")
        assert context.status_code == 200, context.text
        payload = draft(context.json(), account, today)
        payload["living_costs"] = [
            {
                "id": str(uuid4()),
                "account_id": account,
                "category_id": category,
                "mode": "manual",
                "monthly_amount": "10000.0001",
            }
        ]
        with app.state.session_factory.begin() as session:
            before = financial_state(session)
        response = client.post(
            "/api/v1/scenarios/workspaces/compare", headers=csrf(client), json=payload
        )
        assert response.status_code == 200, response.text
        result = response.json()["variants"][0]
        assert result["comparison"]["ending_free_delta"] == "-30000.0002"
        assert isinstance(result["estimates"][0]["monthly_amount"], str)
        assert result["estimates"][0]["coverage_verified"] is False
        solver = client.post(
            "/api/v1/scenarios/workspaces/solve",
            headers=csrf(client),
            json={
                "workspace": payload,
                "variant_id": payload["variants"][0]["id"],
                "decision_id": payload["variants"][0]["decisions"][0]["id"],
                "objective": "maximum_amount",
                "maximum_amount": "100000.0001",
            },
        )
        assert solver.status_code == 200, solver.text
        assert solver.json()["status"] == "found"
        assert client.post("/api/v1/scenarios/workspaces/compare", json=payload).status_code == 403
        payload["variants"][0]["decisions"][0]["amount"] = 0.1
        assert (
            client.post(
                "/api/v1/scenarios/workspaces/compare", headers=csrf(client), json=payload
            ).status_code
            == 422
        )
        with app.state.session_factory.begin() as session:
            assert financial_state(session) == before


@pytest.mark.parametrize("mode", ["manual", "dynamic"])
def test_fund_funded_projection_matches_real_posting_and_dynamic_reserve_refill(
    postgres_database_settings: Settings,
    mode: str,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        account, category, today = initialize(client)
        destination = client.post(
            "/api/v1/accounts",
            headers=csrf(client),
            json={
                "name": "Savings",
                "type": "debit",
                "initial_balance": "0",
            },
        ).json()["id"]
        fund = client.post(
            "/api/v1/funds",
            headers=csrf(client),
            json={
                "name": "Purchase",
                "allocation_percentage": "0",
                "target_amount": "50000",
            },
        ).json()["id"]
        assert (
            client.post(
                "/api/v1/funds/allocations",
                headers=csrf(client),
                json={
                    "account_id": account,
                    "amount": "50000",
                    "occurred_on": today,
                    "allocations": [{"fund_id": fund, "amount": "50000"}],
                },
            ).status_code
            == 201
        )
        if mode == "dynamic":
            assert (
                client.put(
                    "/api/v1/settings/fund-allocation-mode",
                    headers=csrf(client),
                    json={"mode": mode},
                ).status_code
                == 200
            )
            assert (
                client.post(
                    "/api/v1/funds/transfer-and-allocate",
                    headers=csrf(client),
                    json={
                        "source_account_id": account,
                        "destination_account_id": destination,
                        "amount": "10000",
                        "occurred_on": today,
                    },
                ).status_code
                == 201
            )
        context = client.get("/api/v1/scenarios/workspace-context").json()
        payload = draft(context, account, today)
        payload["variants"][0]["decisions"] = [
            {
                "id": str(uuid4()),
                "action": "expense",
                "account_id": account,
                "fund_id": fund,
                "category_id": category,
                "amount": "5000.0001",
                "due_on": today,
            }
        ]
        result = client.post(
            "/api/v1/scenarios/workspaces/compare", headers=csrf(client), json=payload
        )
        assert result.status_code == 200, result.text
        projection = result.json()["variants"][0]
        assert projection["feasible"]
        posted = client.post(
            "/api/v1/operations",
            headers=csrf(client),
            json={
                "type": "expense",
                "account_id": account,
                "fund_id": fund,
                "category_id": category,
                "amount": "5000.0001",
                "occurred_on": today,
            },
        )
        assert posted.status_code == 201, posted.text
        actual = client.get("/api/v1/funds/summary").json()
        comparison = projection["comparison"]
        assert Decimal(actual["total_free"]) == Decimal(
            comparison["alternative"]["free"]["ending_balance"]
        )
        assert sum(
            (Decimal(row["physical_balance"]) for row in actual["accounts"]), Decimal(0)
        ) == Decimal(comparison["alternative"]["total"]["ending_balance"])
        actual_funds = client.get("/api/v1/funds").json()
        assert Decimal(actual_funds[0]["total_balance"]) == Decimal(
            comparison["funds"][0]["alternative"]
        )
        for risk in projection["accounts"]:
            coverage = next(
                row for row in actual["accounts"] if row["account_id"] == risk["account_id"]
            )
            assert Decimal(coverage["free_balance"]) == Decimal(risk["minimum_free"])


def test_saved_program_crud_concurrency_backup_and_legacy_restore(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        account, _, today = initialize(client)
        payload = draft(client.get("/api/v1/scenarios/workspace-context").json(), account, today)
        with app.state.session_factory.begin() as session:
            financial_before = financial_state(session)
            legacy = create_backup(session)
        raw_legacy = legacy.model_dump(mode="json")
        raw_legacy["data"].pop("saved_scenarios")
        legacy = seal_backup(BackupDocument.model_validate(raw_legacy))
        created = client.post(
            "/api/v1/scenarios/saved",
            headers=csrf(client),
            json={"name": "Moving", "workspace": payload},
        )
        assert created.status_code == 201, created.text
        saved = created.json()
        assert saved["workspace"]["variants"][0]["decisions"][0]["amount"] == "10000.0001"
        assert "fund_id" not in saved["workspace"]["variants"][0]["decisions"][0]
        url = f"/api/v1/scenarios/saved/{saved['id']}"

        def update(name: str) -> int:
            return client.put(
                url, headers=csrf(client), json={"name": name, "workspace": payload, "version": 1}
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(update, ["A", "B"])) == [200, 409]
        assert client.delete(url, headers=csrf(client), params={"version": 1}).status_code == 409
        with app.state.session_factory.begin() as session:
            assert financial_state(session) == financial_before
            backup = create_backup(session)
            assert len(backup.data.saved_scenarios) == 1
        assert client.delete(url, headers=csrf(client), params={"version": 2}).status_code == 204
        with app.state.session_factory.begin() as session:
            restored = restore_backup(session, backup)
            assert restored.counts.saved_scenarios == 1
            assert (
                session.get(SavedScenario, UUID(saved["id"])).workspace["variants"][0]["decisions"][
                    0
                ]["amount"]
                == "10000.0001"
            )
        with app.state.session_factory.begin() as session:
            restore_backup(session, legacy)
            assert not session.scalars(select(SavedScenario)).all()
            assert financial_state(session) == financial_before


def test_virtual_schedule_fills_missing_dates_without_resurrecting_exceptions(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        account, category, today = initialize(client)
        start = date.fromisoformat(today)
        rule = client.post(
            "/api/v1/scheduling/rules",
            headers=csrf(client),
            json={
                "type": "expense",
                "amount": "100.0001",
                "account_id": account,
                "category_id": category,
                "frequency": "daily",
                "start_on": today,
                "end_on": str(start + timedelta(days=2)),
            },
        )
        assert rule.status_code == 201, rule.text
        with app.state.session_factory.begin() as session:
            occurrences = list(
                session.scalars(
                    select(ExpectedOccurrence).order_by(ExpectedOccurrence.due_on)
                ).all()
            )
            occurrences[0].status = OccurrenceStatus.CANCELLED
            occurrences[0].manually_modified = True
            session.delete(occurrences[1])
        with app.state.session_factory.begin() as session:
            before = financial_state(session)
        context = client.get("/api/v1/scenarios/workspace-context").json()
        assert len(context["plans"]) == 2
        assert sum(p["origin"] == "virtual" for p in context["plans"]) == 1
        payload = draft(context, account, today)
        payload["variants"][0]["decisions"] = []
        response = client.post(
            "/api/v1/scenarios/workspaces/compare", headers=csrf(client), json=payload
        )
        assert response.status_code == 200, response.text
        assert (
            response.json()["variants"][0]["comparison"]["baseline"]["total"]["expected_expense"]
            == "200.0002"
        )
        with app.state.session_factory.begin() as session:
            assert financial_state(session) == before
        assert (
            client.post("/api/v1/scheduling/materialize", headers=csrf(client)).status_code == 200
        )
        stale = client.post(
            "/api/v1/scenarios/workspaces/compare", headers=csrf(client), json=payload
        )
        assert stale.status_code == 409


def test_history_fact_sources_precision_and_stale_detection(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        account, category, today = initialize(client)
        for offset in range(-6, 0):
            posted = client.post(
                "/api/v1/operations",
                headers=csrf(client),
                json={
                    "type": "expense",
                    "account_id": account,
                    "category_id": category,
                    "amount": "1000.0001",
                    "occurred_on": str(month_shift(date.fromisoformat(today), offset)),
                },
            )
            assert posted.status_code == 201, posted.text
        context = client.get("/api/v1/scenarios/workspace-context").json()
        assert len(context["history"]) == 6
        assert all(f["amount"] == "1000.0001" for f in context["history"])
        payload = draft(context, account, today)
        payload["living_costs"] = [
            {"id": str(uuid4()), "account_id": account, "category_id": category, "mode": "history"}
        ]
        response = client.post(
            "/api/v1/scenarios/workspaces/compare", headers=csrf(client), json=payload
        )
        assert response.status_code == 200, response.text
        evidence = response.json()["baseline_estimates"][0]
        assert evidence["monthly_amount"] == "1000.0001"
        assert evidence["mean_absolute_error"] == "0.0000"
        client.post(
            "/api/v1/operations",
            headers=csrf(client),
            json={
                "type": "expense",
                "account_id": account,
                "category_id": category,
                "amount": "1.0001",
                "occurred_on": today,
            },
        )
        assert (
            client.post(
                "/api/v1/scenarios/workspaces/compare", headers=csrf(client), json=payload
            ).status_code
            == 409
        )


def test_saved_scenarios_migration_keeps_financial_rows(
    postgres_database_settings: Settings,
) -> None:
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        initialize(client)
        with app.state.session_factory.begin() as session:
            before = financial_state(session)
            before.pop("alembic_version")
        command.check(config)
        command.downgrade(config, "0016_oracle_read_index")
        command.upgrade(config, "head")
        command.check(config)
        with app.state.session_factory.begin() as session:
            after = financial_state(session)
            after.pop("alembic_version")
            assert before == after
