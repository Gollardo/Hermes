from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_database_engine
from app.main import create_app
from app.modules.backup.service import (
    BackupInvariantError,
    create_backup,
    restore_backup,
    validate_document,
)
from app.modules.depreciation import service
from app.modules.depreciation.schemas import ContributionCreate
from app.modules.funds.models import Fund

SETUP = {
    "master_password": "correct-master-password",
    "base_currency": "RUB",
    "timezone": "Europe/Moscow",
}


def setup(client: TestClient) -> tuple[dict[str, str], str]:
    assert client.post("/api/v1/setup", json=SETUP).status_code == 201
    headers = {"X-XSRF-TOKEN": str(client.cookies.get("XSRF-TOKEN"))}
    response = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"type": "debit", "name": "Main", "initial_balance": "300000"},
    )
    assert response.status_code == 201
    return headers, str(response.json()["id"])


def create(client: TestClient, headers: dict[str, str], **changes: Any) -> dict[str, Any]:
    payload = dict(
        name="Laptop", cost="200000", purchase_month="2026-08", months=36, inflation="10"
    )
    payload.update(changes)
    response = client.post("/api/v1/depreciation", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_month_end_recalculation_atomic_transfer_backup_and_lifecycle(
    postgres_database_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "application_today", lambda session: "2026-09-17")
    with TestClient(create_app(postgres_database_settings)) as client:
        headers, account = setup(client)
        purchase = create(client, headers)
        assert purchase["target"] == "266200.0000"
        assert purchase["balance"] == "0"
        assert client.get("/api/v1/funds").json() == []
        destination = client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"type": "savings", "name": "Savings", "initial_balance": "0"},
        ).json()["id"]
        payload = dict(
            request_id=str(uuid4()),
            version=1,
            account_id=destination,
            source_account_id=account,
            amount="5000",
        )
        url = f"/api/v1/depreciation/{purchase['id']}/contributions"
        first = client.post(url, headers=headers, json=payload)
        assert first.status_code == 200, first.text
        data = first.json()
        assert data["schedule"][0]["planned"] == "7394.4444"
        assert data["schedule"][0]["remaining"] == "2394.4444"
        assert client.post(url, headers=headers, json=payload).json()["balance"] == "5000.0000"
        changed = dict(payload, amount="6000")
        assert client.post(url, headers=headers, json=changed).status_code == 409
        operation_id = data["history"][0]["operation_id"]
        blocked = client.delete(f"/api/v1/operations/{operation_id}?version=1", headers=headers)
        assert blocked.status_code == 409, blocked.text
        assert blocked.json()["detail"]["code"] == "operation_depreciation_linked"
        summary = client.get("/api/v1/funds/summary").json()
        assert Decimal(summary["total_free"]) == Decimal("295000")
        assert Decimal(summary["depreciation_reserved"]) == Decimal("5000")
        assert Decimal(summary["total_fund_reserved"]) == 0
        monkeypatch.setattr(service, "application_today", lambda session: "2026-10-01")
        current = client.get("/api/v1/depreciation").json()[0]
        assert current["schedule"][1]["planned"] == "7462.8571"
        engine = create_database_engine(postgres_database_settings)
        with Session(engine) as session, session.begin():
            backup = create_backup(session)
            validate_document(backup.data)
            restore_backup(session, backup)
        assert client.get("/api/v1/depreciation").json()[0] == current
        # Source transfer remains immutable; release is an explicit correction fact.
        release = dict(
            request_id=str(uuid4()),
            version=current["version"],
            account_id=destination,
            amount="5000",
            action="release",
        )
        result = client.post(url, headers=headers, json=release)
        assert result.status_code == 200, result.text
        assert Decimal(result.json()["balance"]) == 0
        with Session(engine) as session, session.begin():
            validate_document(create_backup(session).data)
        archived = client.post(
            f"/api/v1/depreciation/{purchase['id']}/archive",
            headers=headers,
            json={"version": result.json()["version"]},
        )
        assert archived.status_code == 200, archived.text
        assert archived.json()["status"] == "archived"
        engine.dispose()


def test_regular_funds_and_dynamic_reserve_cannot_use_managed_savings(
    postgres_database_settings: Settings,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        headers, account = setup(client)
        purchase = create(client, headers, cost="100")
        fund = client.post(
            "/api/v1/funds",
            headers=headers,
            json={"name": "Regular", "allocation_percentage": "100", "target_amount": "100"},
        ).json()
        assert (
            client.put(
                "/api/v1/settings/fund-allocation-mode", headers=headers, json={"mode": "dynamic"}
            ).status_code
            == 200
        )
        preview = client.post(
            "/api/v1/funds/allocation-preview",
            headers=headers,
            json={"account_id": account, "amount": "200"},
        ).json()
        assert [item["fund_id"] for item in preview["allocations"]] == [fund["id"]]
        allocated = client.post(
            "/api/v1/funds/allocations",
            headers=headers,
            json={
                "account_id": account,
                "amount": "200",
                "occurred_on": "2026-09-17",
                "allocations": [{"fund_id": fund["id"], "amount": "100"}],
            },
        )
        assert allocated.status_code == 201, allocated.text
        assert Decimal(client.get("/api/v1/depreciation").json()[0]["balance"]) == 0
        engine = create_database_engine(postgres_database_settings)
        with Session(engine) as session:
            managed_id = session.scalar(select(Fund.id).where(Fund.managed.is_(True)))
        bad = client.post(
            "/api/v1/funds/allocations",
            headers=headers,
            json={
                "account_id": account,
                "amount": "1",
                "occurred_on": "2026-09-17",
                "allocations": [{"fund_id": str(managed_id), "amount": "1"}],
            },
        )
        assert bad.status_code == 404, bad.text
        # Manual-mode switching never assigns managed funds a percentage.
        assert (
            client.put(
                "/api/v1/settings/fund-allocation-mode", headers=headers, json={"mode": "manual"}
            ).status_code
            == 200
        )
        with Session(engine) as session, session.begin():
            document = create_backup(session)
            validate_document(document.data)
            document.data.depreciation_purchases[0].cost = Decimal("99")
            with pytest.raises(BackupInvariantError):
                validate_document(document.data)
        assert purchase["id"]
        engine.dispose()


def test_coverage_target_and_version_failures_roll_back(
    postgres_database_settings: Settings,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        headers, account = setup(client)
        purchase = create(client, headers, cost="400000", inflation="0")
        url = f"/api/v1/depreciation/{purchase['id']}/contributions"
        payload = dict(request_id=str(uuid4()), version=1, account_id=account, amount="300001")
        assert client.post(url, headers=headers, json=payload).status_code == 409
        assert client.get("/api/v1/depreciation").json()[0]["history"] == []
        payload.update(amount="250000")
        assert client.post(url, headers=headers, json=payload).status_code == 200
        # Another ordinary fund cannot reserve the same money.
        other = client.post(
            "/api/v1/funds",
            headers=headers,
            json={
                "name": "Other",
                "allocation_percentage": "0",
                "target_amount": "100000",
                "initial_account_id": account,
                "initial_amount": "100000",
                "initial_occurred_on": "2026-09-17",
            },
        )
        assert other.status_code == 409
        payload.update(request_id=str(uuid4()), amount="1")
        assert (
            client.post(url, headers=headers, json=payload).json()["detail"]["code"]
            == "depreciation_conflict"
        )
        payload.update(version=2, amount="250001", action="release")
        assert client.post(url, headers=headers, json=payload).status_code == 409
        # Failed composed transfer cannot leave money moved on either side.
        destination = client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"type": "savings", "name": "Dest", "initial_balance": "0"},
        ).json()["id"]
        small = create(client, headers, cost="1", inflation="0")
        failed = client.post(
            f"/api/v1/depreciation/{small['id']}/contributions",
            headers=headers,
            json=dict(
                request_id=str(uuid4()),
                version=1,
                account_id=destination,
                source_account_id=account,
                amount="2",
            ),
        )
        assert failed.status_code == 409
        assert (
            Decimal(
                next(a for a in client.get("/api/v1/accounts").json() if a["id"] == destination)[
                    "balance"
                ]
            )
            == 0
        )


def test_concurrent_retry_posts_once(postgres_database_settings: Settings) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        headers, account = setup(client)
        purchase = create(client, headers)
        payload = ContributionCreate(
            request_id=uuid4(), version=1, account_id=UUID(account), amount=Decimal("100")
        )
        engine = create_database_engine(postgres_database_settings)

        def post() -> str:
            with Session(engine) as session, session.begin():
                return service.contribute(session, UUID(purchase["id"]), payload).balance

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: post(), range(2)))
        assert results == ["100.0000", "100.0000"]
        assert len(client.get("/api/v1/depreciation").json()[0]["history"]) == 1
        engine.dispose()


def test_access_validation_and_migration_guard(postgres_database_settings: Settings) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        assert client.get("/api/v1/depreciation").status_code == 401
        headers, _ = setup(client)
        assert client.post("/api/v1/depreciation", json={}).status_code == 403
        preview = client.post(
            "/api/v1/depreciation/preview",
            headers=headers,
            json=dict(
                name="Laptop", cost="200000", inflation="10", months=36, purchase_month="2026-08"
            ),
        )
        assert preview.status_code == 200
        assert preview.json()["target"] == "266200.0000"
        assert client.get("/api/v1/depreciation").json() == []
        invalid = client.post(
            "/api/v1/depreciation",
            headers=headers,
            json=dict(
                name="Laptop", cost=200000.5, inflation="10", months=36, purchase_month="2026-08"
            ),
        )
        assert invalid.status_code == 422
        create(client, headers)
        command.check(Config("alembic.ini"))
        with pytest.raises(Exception, match="Cannot downgrade while depreciation purchases exist"):
            command.downgrade(Config("alembic.ini"), "0016_fund_release")


def test_forecast_and_protected_backup_include_actual_reservations_only(
    postgres_database_settings: Settings,
) -> None:
    from app.modules.backup.service import create_hermes_backup, open_backup

    with TestClient(create_app(postgres_database_settings)) as client:
        headers, account = setup(client)
        purchase = create(client, headers)
        contributed = client.post(
            f"/api/v1/depreciation/{purchase['id']}/contributions",
            headers=headers,
            json=dict(request_id=str(uuid4()), version=1, account_id=account, amount="1000"),
        )
        assert contributed.status_code == 200
        free = client.get("/api/v1/forecast?balance_mode=free").json()
        total = client.get("/api/v1/forecast?balance_mode=total").json()
        assert Decimal(free["starting_balance"]) == Decimal("299000")
        assert Decimal(total["starting_balance"]) == Decimal("300000")
        assert client.get("/api/v1/forecast/funds").json()["series"] == []
        engine = create_database_engine(postgres_database_settings)
        with Session(engine) as session, session.begin():
            envelope = create_hermes_backup(session, "separate-backup-password")
            document = open_backup(envelope.model_dump(mode="json"), "separate-backup-password")
            assert len(document.data.depreciation_purchases) == 1
            restore_backup(session, document)
        assert client.get("/api/v1/depreciation").json()[0]["balance"] == "1000.0000"
        engine.dispose()
