from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Event
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.modules.operations.contracts import account_balances
from app.modules.scenarios import snapshot as snapshot_module
from app.modules.scheduling.models import ExpectedOccurrence

SETUP = {
    "master_password": "oracle-test-password",
    "base_currency": "RUB",
    "timezone": "Europe/Moscow",
}


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": str(client.cookies.get("XSRF-TOKEN"))}


def initialize(client: TestClient) -> tuple[str, str, str]:
    assert client.post("/api/v1/setup", json=SETUP).status_code == 201
    account = client.post(
        "/api/v1/accounts",
        headers=csrf(client),
        json={"name": "Main", "type": "debit", "initial_balance": "1000.0001"},
    ).json()["id"]
    category = client.post(
        "/api/v1/categories", headers=csrf(client), json={"name": "Salary", "type": "income"}
    ).json()["id"]
    today = client.get("/api/v1/settings").json()["application_today"]
    response = client.post(
        "/api/v1/scheduling/rules",
        headers=csrf(client),
        json={
            "type": "income",
            "amount": "100",
            "account_id": account,
            "category_id": category,
            "frequency": "daily",
            "start_on": today,
            "end_on": today,
        },
    )
    assert response.status_code == 201, response.text
    return account, category, today


def financial_state(session: Session) -> dict[str, list[str]]:
    # Exclude authentication metadata only; include settings and import receipts.
    inspector = inspect(session.get_bind())
    names = inspector.get_table_names()
    return {
        name: sorted(session.scalars(text(f'SELECT row_to_json(t)::text FROM "{name}" t')).all())
        for name in names
        if name not in {"auth_sessions", "login_throttle", "owner_credentials"}
    }


def test_oracle_api_exact_no_financial_side_effects_and_stale_guard(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.get("/api/v1/scenarios/context").status_code == 401
        account, _, today = initialize(client)
        context = client.get("/api/v1/scenarios/context")
        assert context.status_code == 200, context.text
        source = context.json()
        assert source["source_policy"] == "materialized_plans_only"
        payload = {
            "action": "expense",
            "account_id": account,
            "amount": "1100.0002",
            "due_on": today,
            "snapshot_id": source["snapshot_id"],
            "stop_loss": "50",
        }
        assert client.post("/api/v1/scenarios/compare", json=payload).status_code == 403
        with app.state.session_factory.begin() as session:
            before = financial_state(session)
        response = client.post("/api/v1/scenarios/compare", headers=csrf(client), json=payload)
        assert response.status_code == 200, response.text
        result = response.json()
        assert Decimal(result["ending_free_delta"]) == Decimal("-1100.0002")
        assert Decimal(result["alternative"]["free"]["minimum_balance"]) == Decimal("-0.0001")
        assert result["alternative"]["zero_risk"]["windows"][0]["from_on"] == today
        assert result["baseline"]["free"] == client.get("/api/v1/forecast").json()
        invalid = client.post(
            "/api/v1/scenarios/compare", headers=csrf(client), json={**payload, "amount": 0.5}
        )
        assert invalid.status_code == 422
        with app.state.session_factory.begin() as session:
            assert before == financial_state(session)
        # A source mutation must invalidate both branches, preserving explicit recalculation.
        occurrence = source["plans"][0]
        confirmed = client.post(
            f"/api/v1/scheduling/occurrences/{occurrence['id']}/confirm",
            headers=csrf(client),
            json={"version": occurrence["version"]},
        )
        assert confirmed.status_code == 200
        stale = client.post("/api/v1/scenarios/compare", headers=csrf(client), json=payload)
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "scenario_stale"


@pytest.mark.parametrize("mutation", ["confirm", "postpone", "post", "new_plan", "fund"])
def test_mvcc_snapshot_remains_coherent_during_concurrent_mutations(
    postgres_database_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        account, category, today = initialize(client)
        source = client.get("/api/v1/scenarios/context").json()
        occurrence = source["plans"][0]
        payload = {
            "action": "expense",
            "account_id": account,
            "amount": "10",
            "due_on": today,
            "snapshot_id": source["snapshot_id"],
        }
        paused, release = Event(), Event()

        def pause_balance(session: Session, ids: set[UUID]) -> dict[UUID, Decimal]:
            paused.set()
            assert release.wait(10)
            return account_balances(session, ids)

        monkeypatch.setattr(snapshot_module, "account_balances", pause_balance)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                client.post, "/api/v1/scenarios/compare", headers=csrf(client), json=payload
            )
            assert paused.wait(10)
            try:
                if mutation == "confirm":
                    changed = client.post(
                        f"/api/v1/scheduling/occurrences/{occurrence['id']}/confirm",
                        headers=csrf(client),
                        json={"version": occurrence["version"]},
                    )
                elif mutation == "postpone":
                    changed = client.post(
                        f"/api/v1/scheduling/occurrences/{occurrence['id']}/postpone",
                        headers=csrf(client),
                        json={
                            "version": occurrence["version"],
                            "due_on": str(date.fromisoformat(today) + timedelta(days=3)),
                        },
                    )
                elif mutation == "post":
                    changed = client.post(
                        "/api/v1/operations",
                        headers=csrf(client),
                        json={
                            "type": "income",
                            "account_id": account,
                            "category_id": category,
                            "amount": "20",
                            "occurred_on": today,
                        },
                    )
                elif mutation == "new_plan":
                    changed = client.post(
                        "/api/v1/scheduling/rules",
                        headers=csrf(client),
                        json={
                            "type": "income",
                            "account_id": account,
                            "category_id": category,
                            "amount": "20",
                            "frequency": "daily",
                            "start_on": today,
                            "end_on": today,
                        },
                    )
                else:
                    changed = client.post(
                        "/api/v1/funds",
                        headers=csrf(client),
                        json={
                            "name": "Reserve",
                            "allocation_percentage": "50",
                            "initial_account_id": account,
                            "initial_amount": "30",
                            "initial_occurred_on": today,
                        },
                    )
                assert changed.status_code in {200, 201}, changed.text
            finally:
                release.set()
            response = future.result(10)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["snapshot_id"] == source["snapshot_id"]
        assert result["baseline"]["free"]["starting_balance"] == "1000.0001"
        assert result["baseline"]["free"]["ending_balance"] == "1100.0001"
        assert result["alternative"]["free"]["ending_balance"] == "1090.0001"
        assert (
            client.get("/api/v1/scenarios/context").json()["snapshot_id"] != source["snapshot_id"]
        )


def test_database_rejects_writes_in_projection_session(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        initialize(client)
        with (
            app.state.database_engine.connect().execution_options(
                isolation_level="REPEATABLE READ", postgresql_readonly=True
            ) as connection,
            Session(bind=connection) as session,
            session.begin(),
        ):
            assert session.scalar(text("SHOW transaction_read_only")) == "on"
            assert session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
            with pytest.raises(DBAPIError):
                session.execute(text("DELETE FROM expected_occurrences"))
            session.rollback()


def test_oracle_does_not_materialize_missing_plans_and_versions_are_exposed(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        initialize(client)
        with app.state.session_factory.begin() as session:
            session.query(ExpectedOccurrence).delete()
        context = client.get("/api/v1/scenarios/context").json()
        assert context["plans"] == []
        with app.state.session_factory.begin() as session:
            assert session.query(ExpectedOccurrence).count() == 0


def test_oracle_index_migration_round_trip_preserves_data(
    postgres_database_settings: Settings,
) -> None:
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        initialize(client)
        with app.state.session_factory.begin() as session:
            before = session.query(ExpectedOccurrence).count()
        command.check(config)
        command.downgrade(config, "0015_statement_imports")
        with app.state.database_engine.connect() as connection:
            assert not any(
                index["name"] == "ix_occurrences_oracle_due"
                for index in inspect(connection).get_indexes("expected_occurrences")
            )
        command.upgrade(config, "head")
        command.check(config)
        with app.state.session_factory.begin() as session:
            assert session.query(ExpectedOccurrence).count() == before


def test_dynamic_overflow_matches_actual_posting_and_existing_forecast(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        account, _, today = initialize(client)
        target = client.post(
            "/api/v1/accounts",
            headers=csrf(client),
            json={"name": "Savings", "type": "savings", "initial_balance": "0"},
        ).json()["id"]
        assert (
            client.post(
                "/api/v1/funds",
                headers=csrf(client),
                json={
                    "name": "Small target",
                    "allocation_percentage": "100",
                    "target_amount": "10",
                },
            ).status_code
            == 201
        )
        assert (
            client.put(
                "/api/v1/settings/fund-allocation-mode",
                headers=csrf(client),
                json={"mode": "dynamic"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/v1/scheduling/rules",
                headers=csrf(client),
                json={
                    "type": "transfer",
                    "account_id": account,
                    "destination_account_id": target,
                    "amount": "100",
                    "allocate_to_funds": True,
                    "frequency": "daily",
                    "start_on": today,
                    "end_on": today,
                },
            ).status_code
            == 201
        )
        source = client.get("/api/v1/scenarios/context").json()
        plan = next(item for item in source["plans"] if item["type"] == "transfer")
        response = client.post(
            "/api/v1/scenarios/compare",
            headers=csrf(client),
            json={
                "action": "amount",
                "occurrence_id": plan["id"],
                "version": plan["version"],
                "amount": "120",
                "snapshot_id": source["snapshot_id"],
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["baseline"]["free"] == client.get("/api/v1/forecast").json()
        assert Decimal(result["baseline"]["free"]["ending_balance"]) == Decimal("1000.0001")
        assert Decimal(result["ending_free_delta"]) == -20
        assert Decimal(result["reserve"]["baseline"]) == 90
        assert Decimal(result["reserve"]["alternative"]) == 110
        assert (
            client.post(
                f"/api/v1/scheduling/occurrences/{plan['id']}/confirm",
                headers=csrf(client),
                json={"version": plan["version"]},
            ).status_code
            == 200
        )
        after = client.get("/api/v1/forecast").json()
        assert after["ending_balance"] == result["baseline"]["free"]["ending_balance"]
