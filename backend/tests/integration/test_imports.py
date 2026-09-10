import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.database import create_database_engine, create_session_factory
from app.main import create_app
from app.modules.backup.service import create_backup, restore_backup
from app.modules.imports.models import ImportReceipt
from app.modules.operations.models import FinancialOperation

SETUP_PAYLOAD = {
    "master_password": "correct-master-password",
    "base_currency": "RUB",
    "timezone": "Europe/Moscow",
}


def _headers(client: TestClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": str(client.cookies.get("XSRF-TOKEN"))}


def _account(client: TestClient, headers: dict[str, str], name: str, balance: str) -> str:
    response = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"type": "debit", "name": name, "initial_balance": balance},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _category(client: TestClient, headers: dict[str, str], name: str, kind: str) -> str:
    response = client.post("/api/v1/categories", headers=headers, json={"name": name, "type": kind})
    assert response.status_code == 201
    return str(response.json()["id"])


def source(
    text: str = "amount;description;status\n-10.50;Coffee;pending\n-20;Food;done\n",
) -> dict[str, Any]:
    return dict(
        filename="test.csv",
        content=base64.b64encode(text.encode()).decode(),
        mapping=dict(amount=0, description=1, direction=None, currency=None),
    )


def decision(account: str, category: str, row: int = 2, amount: str = "10.50") -> dict[str, Any]:
    return dict(
        row=row,
        statement_account_id=account,
        action="new",
        operation=dict(
            type="expense",
            occurred_on="2026-01-01",
            amount=amount,
            description="Coffee",
            account_id=account,
            category_id=category,
        ),
    )


def test_import_preview_commit_retry_backup_and_rollback(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/imports/inspect", json=source()).status_code in {401, 403}
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Bank", "100")
        category = _category(client, headers, "Food", "expense")
        request = source()
        preview = client.post(
            "/api/v1/imports/preview",
            headers=headers,
            json={**request, "account_id": account, "occurred_on": "2026-01-01"},
        )
        assert preview.status_code == 200, preview.text
        assert len(preview.json()["rows"]) == 2
        assert preview.json()["rows"][0]["raw"][2] == "pending"
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "100.0000"
        assert (
            client.put(
                "/api/v1/imports/profiles",
                headers=headers,
                json={"name": "Example", "mapping": request["mapping"]},
            ).status_code
            == 200
        )
        body = {**request, "decisions": [decision(account, category)]}
        response = client.post("/api/v1/imports/commit", headers=headers, json=body)
        assert response.status_code == 200, response.text
        operation_id = response.json()["results"][0]["operation_id"]
        again = client.post("/api/v1/imports/commit", headers=headers, json=body)
        assert again.status_code == 200 and again.json()["results"][0]["reused"]
        assert (
            client.get("/api/v1/operations/" + operation_id).json()["occurred_on"] == "2026-01-01"
        )
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "89.5000"
        # One valid row followed by an impossible expense must roll back both receipts and money.
        failing = source("amount;description\n-1;Small\n-999;Large\n")
        result = client.post(
            "/api/v1/imports/commit",
            headers=headers,
            json={
                **failing,
                "decisions": [
                    decision(account, category, 2, "1"),
                    decision(account, category, 3, "999"),
                ],
            },
        )
        assert result.status_code == 409, result.text
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "89.5000"
        factory = create_session_factory(create_database_engine(postgres_database_settings))
        with factory.begin() as session:
            backup = create_backup(session)
            assert len(backup.data.import_receipts) == 1
            assert len(backup.data.import_profiles) == 1
            restore_backup(session, backup)
        from alembic import command
        from alembic.config import Config

        with pytest.raises(RuntimeError, match="Import receipts"):
            command.downgrade(Config("alembic.ini"), "0014_one_off_plans")

        assert client.post("/api/v1/imports/commit", headers=headers, json=body).json()["results"][
            0
        ]["reused"]
        # Changed decision cannot reuse the same source silently.
        body["decisions"][0]["operation"]["occurred_on"] = "2026-01-02"
        assert client.post("/api/v1/imports/commit", headers=headers, json=body).status_code == 422


def test_plan_confirmation_uses_user_date_and_existing_fact_without_reposting(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        client.post("/api/v1/setup", json=SETUP_PAYLOAD)
        headers = _headers(client)
        account = _account(client, headers, "Bank", "100")
        category = _category(client, headers, "Food", "expense")
        future = (date.today() + timedelta(days=2)).isoformat()
        plan_response = client.post(
            "/api/v1/scheduling/one-off-plans",
            headers=headers,
            json=dict(
                type="expense",
                scheduled_on=future,
                amount="10",
                account_id=account,
                category_id=category,
                description="Coffee",
            ),
        )
        assert plan_response.status_code == 201, plan_response.text
        plan = plan_response.json()
        entry = decision(account, category)
        entry.update(action="plan", occurrence_id=plan["id"], occurrence_version=plan["version"])
        response = client.post(
            "/api/v1/imports/commit", headers=headers, json={**source(), "decisions": [entry]}
        )
        assert response.status_code == 200, response.text
        op = response.json()["results"][0]["operation_id"]
        assert client.get("/api/v1/operations/" + op).json()["occurred_on"] == "2026-01-01"
        # A fresh plan can attach to a separately entered matching fact without a ledger write.
        plan2 = client.post(
            "/api/v1/scheduling/one-off-plans",
            headers=headers,
            json=dict(
                type="expense",
                scheduled_on=future,
                amount="20",
                account_id=account,
                category_id=category,
            ),
        ).json()
        payload = decision(account, category, 3, "20")["operation"]
        fact = client.post("/api/v1/operations", headers=headers, json=payload).json()
        entry2 = decision(account, category, 3, "20")
        entry2.update(
            action="plan",
            occurrence_id=plan2["id"],
            occurrence_version=plan2["version"],
            existing_id=fact["id"],
            existing_version=fact["version"],
        )
        before = client.get("/api/v1/accounts").json()
        linked = client.post(
            "/api/v1/imports/commit", headers=headers, json={**source(), "decisions": [entry2]}
        )
        assert linked.status_code == 200, linked.text
        assert client.get("/api/v1/accounts").json() == before


def test_concurrent_import_and_invalid_currency_future_date(
    postgres_database_settings: Settings,
) -> None:
    from app.application.imports import commit
    from app.modules.imports.schemas import CommitRequest

    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        client.post("/api/v1/setup", json=SETUP_PAYLOAD)
        headers = _headers(client)
        account = _account(client, headers, "Bank", "100")
        category = _category(client, headers, "Food", "expense")
        body = {**source(), "decisions": [decision(account, category)]}
        factory = create_session_factory(create_database_engine(postgres_database_settings))

        def run() -> dict[str, Any]:
            with factory.begin() as session:
                return commit(session, CommitRequest.model_validate(body))

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: run(), range(2)))
        assert results[0]["results"][0]["operation_id"] == results[1]["results"][0]["operation_id"]
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(ImportReceipt)) == 1
            assert (
                session.get(FinancialOperation, UUID(results[0]["results"][0]["operation_id"]))
                is not None
            )
        body = source("amount;description;currency\n-10.50;Coffee;USD\n")
        body["mapping"]["currency"] = 2
        body["decisions"] = [decision(account, category)]
        assert client.post("/api/v1/imports/commit", headers=headers, json=body).status_code == 422
        body = source("amount;description\n-10.50;Future\n")
        item = decision(account, category)
        item["operation"]["occurred_on"] = (date.today() + timedelta(days=2)).isoformat()
        body["decisions"] = [item]
        assert client.post("/api/v1/imports/commit", headers=headers, json=body).status_code == 409


def test_matching_explains_candidates_and_preview_is_read_only(
    postgres_database_settings: Settings,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        client.post("/api/v1/setup", json=SETUP_PAYLOAD)
        headers = _headers(client)
        account = _account(client, headers, "Bank", "100")
        category = _category(client, headers, "Food", "expense")
        client.post(
            "/api/v1/operations", headers=headers, json=decision(account, category)["operation"]
        )
        response = client.post(
            "/api/v1/imports/preview",
            headers=headers,
            json={**source(), "account_id": account, "occurred_on": "2026-01-01"},
        )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        reasons = response.json()["rows"][0]["facts"][0]["reasons"]
        assert reasons == ["amount", "description", "date"]
        factory = create_session_factory(create_database_engine(postgres_database_settings))
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(ImportReceipt)) == 0


def test_stale_plan_rolls_back_and_deleted_fact_is_not_recreated(
    postgres_database_settings: Settings,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        client.post("/api/v1/setup", json=SETUP_PAYLOAD)
        headers = _headers(client)
        account = _account(client, headers, "Bank", "100")
        category = _category(client, headers, "Food", "expense")
        plan = client.post(
            "/api/v1/scheduling/one-off-plans",
            headers=headers,
            json=dict(
                type="expense",
                scheduled_on=(date.today() + timedelta(days=2)).isoformat(),
                amount="10",
                account_id=account,
                category_id=category,
            ),
        ).json()
        entry = decision(account, category)
        entry.update(
            action="plan", occurrence_id=plan["id"], occurrence_version=plan["version"] + 1
        )
        response = client.post(
            "/api/v1/imports/commit", headers=headers, json={**source(), "decisions": [entry]}
        )
        assert response.status_code == 422
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "100.0000"
        body = {**source(), "decisions": [decision(account, category)]}
        result = client.post("/api/v1/imports/commit", headers=headers, json=body).json()
        op = result["results"][0]["operation_id"]
        assert (
            client.delete(
                "/api/v1/operations/" + op, headers=headers, params={"version": 1}
            ).status_code
            == 204
        )
        repeated = client.post("/api/v1/imports/commit", headers=headers, json=body)
        assert repeated.status_code == 200
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "100.0000"
        preview = client.post(
            "/api/v1/imports/preview",
            headers=headers,
            json={**source(), "account_id": account, "occurred_on": "2026-01-01"},
        ).json()
        assert preview["rows"][0]["imported_deleted"]


def test_transfer_second_statement_links_without_double_movement(
    postgres_database_settings: Settings,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        client.post("/api/v1/setup", json=SETUP_PAYLOAD)
        headers = _headers(client)
        source_id = _account(client, headers, "Bank", "100")
        destination_id = _account(client, headers, "Savings", "0")
        entry = dict(
            row=2,
            statement_account_id=source_id,
            action="new",
            operation=dict(
                type="transfer",
                occurred_on="2026-01-01",
                amount="10.50",
                account_id=source_id,
                destination_account_id=destination_id,
                description="Transfer",
            ),
        )
        result = client.post(
            "/api/v1/imports/commit", headers=headers, json={**source(), "decisions": [entry]}
        )
        assert result.status_code == 200, result.text
        op = result.json()["results"][0]["operation_id"]
        entry.update(
            action="existing",
            statement_account_id=destination_id,
            existing_id=op,
            existing_version=1,
        )
        incoming = source("amount;description\n10.50;Transfer\n")
        response = client.post(
            "/api/v1/imports/commit", headers=headers, json={**incoming, "decisions": [entry]}
        )
        assert response.status_code == 200, response.text
        balances = {a["id"]: a["balance"] for a in client.get("/api/v1/accounts").json()}
        assert balances == {source_id: "89.5000", destination_id: "10.5000"}


def test_migration_metadata_matches_and_guarded_downgrade(
    postgres_database_settings: Settings,
) -> None:
    from alembic import command
    from alembic.config import Config

    command.check(Config("alembic.ini"))
    command.downgrade(Config("alembic.ini"), "0014_one_off_plans")
    command.upgrade(Config("alembic.ini"), "head")
    command.check(Config("alembic.ini"))


def test_import_fund_coverage_and_exact_fund_expense(postgres_database_settings: Settings) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        client.post("/api/v1/setup", json=SETUP_PAYLOAD)
        headers = _headers(client)
        account = _account(client, headers, "Bank", "100")
        category = _category(client, headers, "Food", "expense")
        fund = client.post(
            "/api/v1/funds",
            headers=headers,
            json=dict(
                name="Food reserve",
                allocation_percentage="50",
                initial_account_id=account,
                initial_amount="95",
                initial_occurred_on="2026-01-01",
            ),
        )
        assert fund.status_code == 201, fund.text
        body = {**source(), "decisions": [decision(account, category)]}
        response = client.post("/api/v1/imports/commit", headers=headers, json=body)
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["row"] == 2
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "100.0000"
        body["decisions"][0]["operation"]["fund_id"] = fund.json()["id"]
        posted = client.post("/api/v1/imports/commit", headers=headers, json=body)
        assert posted.status_code == 200, posted.text
        assert client.get("/api/v1/funds").json()[0]["total_balance"] == "84.5000"


def test_import_recurring_snapshot_preserves_rule_and_siblings(
    postgres_database_settings: Settings,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        client.post("/api/v1/setup", json=SETUP_PAYLOAD)
        headers = _headers(client)
        account = _account(client, headers, "Bank", "100")
        category = _category(client, headers, "Food", "expense")
        today = date.today()
        response = client.post(
            "/api/v1/scheduling/rules",
            headers=headers,
            json=dict(
                type="expense",
                frequency="daily",
                start_on=today.isoformat(),
                end_on=(today + timedelta(days=2)).isoformat(),
                amount="10",
                account_id=account,
                category_id=category,
                description="Coffee",
            ),
        )
        assert response.status_code == 201, response.text
        rules_before = client.get("/api/v1/scheduling/rules").json()
        page = client.get("/api/v1/scheduling/occurrences").json()
        plan = page["items"][0]
        entry = decision(account, category)
        entry.update(action="plan", occurrence_id=plan["id"], occurrence_version=plan["version"])
        posted = client.post(
            "/api/v1/imports/commit", headers=headers, json={**source(), "decisions": [entry]}
        )
        assert posted.status_code == 200, posted.text
        assert client.get("/api/v1/scheduling/rules").json() == rules_before
        after = client.get("/api/v1/scheduling/occurrences").json()["items"]
        for before in page["items"]:
            current = next(p for p in after if p["id"] == before["id"])
            if before["id"] == plan["id"]:
                assert current["status"] == "confirmed"
                assert current["amount"] == "10.5000"
                assert current["due_on"] == before["due_on"]
            else:
                assert current == before
