from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

PASSWORD = "correct-master-password"


@pytest.fixture
def release_setup(
    postgres_database_settings: Settings,
) -> Iterator[tuple[TestClient, dict[str, str], dict[str, Any]]]:
    with TestClient(create_app(postgres_database_settings)) as client:
        assert (
            client.post(
                "/api/v1/setup",
                json={
                    "master_password": PASSWORD,
                    "base_currency": "RUB",
                    "timezone": "UTC",
                },
            ).status_code
            == 201
        )
        headers = {"X-XSRF-TOKEN": str(client.cookies.get("XSRF-TOKEN"))}

        def account(name: str, amount: str) -> str:
            response = client.post(
                "/api/v1/accounts",
                headers=headers,
                json={
                    "type": "debit",
                    "name": name,
                    "initial_balance": amount,
                },
            )
            assert response.status_code == 201, response.text
            return str(response.json()["id"])

        source = account("Savings", "100")
        destination = account("Salary", "70")
        fund = client.post(
            "/api/v1/funds",
            headers=headers,
            json={
                "name": "Purchase",
                "allocation_percentage": "100",
                "target_amount": "100",
                "initial_account_id": source,
                "initial_amount": "100",
                "initial_occurred_on": date.today().isoformat(),
            },
        )
        assert fund.status_code == 201, fund.text
        payload = dict(
            request_id=str(uuid4()),
            account_id=source,
            destination_account_id=destination,
            fund_id=fund.json()["id"],
            amount="30.1234",
            occurred_on=date.today().isoformat(),
            description="Compensation",
        )
        yield client, headers, payload


def balances(client: TestClient) -> dict[str, Any]:
    return dict(client.get("/api/v1/funds/summary").json())


def test_release_transfer_and_replay_are_exact_and_reversible(release_setup: Any) -> None:
    client, headers, payload = release_setup
    before = balances(client)
    response = client.post("/api/v1/funds/releases", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    result = response.json()
    after = balances(client)
    accounts = {a["account_id"]: a for a in after["accounts"]}
    assert accounts[payload["account_id"]]["physical_balance"] == "69.8766"
    assert accounts[payload["account_id"]]["free_balance"] == "0.0000"
    assert accounts[payload["destination_account_id"]]["free_balance"] == "100.1234"
    assert after["total_fund_reserved"] == "69.8766"
    assert sum(Decimal(a["physical_balance"]) for a in after["accounts"]) == Decimal("170")
    assert client.post("/api/v1/funds/releases", headers=headers, json=payload).json() == result
    assert balances(client) == after
    conflict = client.post(
        "/api/v1/funds/releases", headers=headers, json={**payload, "amount": "20"}
    )
    assert conflict.status_code == 409
    assert balances(client) == after
    operation_id = result["operation_id"]
    operation = client.get(f"/api/v1/operations/{operation_id}").json()
    assert operation["type"] == "transfer"
    assert operation["fund_movements"] == []
    update = client.put(
        f"/api/v1/operations/{operation_id}",
        headers=headers,
        json={
            "type": "transfer",
            "account_id": payload["account_id"],
            "destination_account_id": payload["destination_account_id"],
            "amount": payload["amount"],
            "occurred_on": payload["occurred_on"],
            "version": 1,
        },
    )
    assert update.status_code == 409
    assert update.json()["detail"]["code"] == "operation_fund_release_linked"
    assert (
        client.delete(f"/api/v1/operations/{operation_id}?version=2", headers=headers).status_code
        == 409
    )
    assert (
        client.delete(f"/api/v1/operations/{operation_id}?version=1", headers=headers).status_code
        == 204
    )
    assert balances(client) == before


def test_same_account_release_creates_no_physical_operation(release_setup: Any) -> None:
    client, headers, payload = release_setup
    payload["destination_account_id"] = payload["account_id"]
    count = client.get("/api/v1/operations").json()["total"]
    result = client.post("/api/v1/funds/releases", headers=headers, json=payload)
    assert result.status_code == 201
    assert result.json()["operation_id"] is None
    assert client.get("/api/v1/operations").json()["total"] == count
    summary = balances(client)
    account = next(a for a in summary["accounts"] if a["account_id"] == payload["account_id"])
    assert account["physical_balance"] == "100.0000"
    assert account["free_balance"] == "30.1234"
    history = client.get("/api/v1/funds/history").json()["items"]
    assert sum(item["type"] == "fund_release" for item in history) == 1


@pytest.mark.parametrize(
    "change,status",
    [
        ({"amount": "100.0001"}, 409),
        ({"amount": "0"}, 422),
        ({"amount": "-1"}, 422),
        ({"amount": 1.2}, 422),
        ({"amount": "0.00001"}, 422),
        ({"occurred_on": (date.today() + timedelta(days=1)).isoformat()}, 409),
        ({"destination_account_id": str(uuid4())}, 409),
        ({"fund_id": str(uuid4())}, 404),
    ],
)
def test_invalid_release_rolls_back(
    release_setup: Any, change: dict[str, Any], status: int
) -> None:
    client, headers, payload = release_setup
    before = balances(client)
    count = client.get("/api/v1/operations").json()["total"]
    response = client.post("/api/v1/funds/releases", headers=headers, json={**payload, **change})
    assert response.status_code == status, response.text
    assert balances(client) == before
    assert client.get("/api/v1/operations").json()["total"] == count


def test_release_rejects_archived_destination(release_setup: Any) -> None:
    client, headers, payload = release_setup
    assert (
        client.post(
            f"/api/v1/accounts/{payload['destination_account_id']}/archive", headers=headers
        ).status_code
        == 200
    )
    before = balances(client)
    assert client.post("/api/v1/funds/releases", headers=headers, json=payload).status_code == 409
    assert balances(client) == before


def test_dynamic_refill_is_reversed_with_transfer(release_setup: Any) -> None:
    client, headers, payload = release_setup
    assert (
        client.put(
            "/api/v1/settings/fund-allocation-mode", headers=headers, json={"mode": "dynamic"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/funds/allocations",
            headers=headers,
            json={
                "account_id": payload["destination_account_id"],
                "amount": "50",
                "occurred_on": payload["occurred_on"],
                "allocations": [],
            },
        ).status_code
        == 201
    )
    before = balances(client)
    result = client.post("/api/v1/funds/releases", headers=headers, json=payload)
    assert result.status_code == 201, result.text
    after = balances(client)
    assert after["total_fund_reserved"] == "100.0000"
    assert after["total_reserve"] == "19.8766"
    assert Decimal(after["total_free"]) - Decimal(before["total_free"]) == Decimal("30.1234")
    assert (
        client.delete(
            f"/api/v1/operations/{result.json()['operation_id']}?version=1", headers=headers
        ).status_code
        == 204
    )
    assert balances(client) == before


def test_reversal_cannot_restore_an_archived_fund(release_setup: Any) -> None:
    client, headers, payload = release_setup
    payload["amount"] = "100"
    result = client.post("/api/v1/funds/releases", headers=headers, json=payload)
    assert result.status_code == 201
    assert (
        client.post(
            f"/api/v1/funds/{payload['fund_id']}/archive", headers=headers, json={"version": 1}
        ).status_code
        == 200
    )
    before = balances(client)
    response = client.delete(
        f"/api/v1/operations/{result.json()['operation_id']}?version=1", headers=headers
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "archived_fund_balance"
    assert balances(client) == before


@pytest.mark.parametrize("same_request", [False, True])
def test_concurrent_releases_serialize(release_setup: Any, same_request: bool) -> None:
    owner, _, payload = release_setup
    payload["amount"] = "60"
    barrier = Barrier(2)

    def release(index: int) -> int:
        with TestClient(owner.app) as client:
            assert (
                client.post("/api/v1/auth/login", json={"master_password": PASSWORD}).status_code
                == 200
            )
            headers = {"X-XSRF-TOKEN": str(client.cookies.get("XSRF-TOKEN"))}
            body = {
                **payload,
                "request_id": payload["request_id"] if same_request else str(uuid4()),
            }
            barrier.wait(timeout=10)
            return client.post("/api/v1/funds/releases", headers=headers, json=body).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(release, range(2)))
    assert sorted(statuses) == ([201, 201] if same_request else [201, 409])
    assert balances(owner)["total_fund_reserved"] == "40.0000"


@pytest.mark.parametrize("cross_account", [False, True])
def test_release_backup_roundtrip_and_invalid_shapes(
    release_setup: Any, cross_account: bool
) -> None:
    from copy import deepcopy

    from app.modules.backup.schemas import BackupDocument
    from app.modules.backup.service import BackupInvariantError, validate_document

    client, headers, payload = release_setup
    if not cross_account:
        payload["destination_account_id"] = None
    assert client.post("/api/v1/funds/releases", headers=headers, json=payload).status_code == 201
    before = balances(client)
    backup = client.get("/api/v1/backup/export").json()
    document = BackupDocument.model_validate(backup)
    validate_document(document.data)
    bad = deepcopy(document.data)
    movement = next(m for m in bad.fund_movements if str(m.event_id) == payload["request_id"])
    movement.amount = abs(movement.amount)
    with pytest.raises(BackupInvariantError):
        validate_document(bad)
    if cross_account:
        bad = deepcopy(document.data)
        movement = next(m for m in bad.fund_movements if str(m.event_id) == payload["request_id"])
        movement.amount = Decimal("-20")
        with pytest.raises(BackupInvariantError, match="Fund release transfer cause"):
            validate_document(bad)
    response = client.post(
        "/api/v1/backup/restore",
        headers=headers,
        json={
            "backup": backup,
            "confirmation": "ЗАМЕНИТЬ ВСЕ ДАННЫЕ",
            "master_password": PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    assert balances(client) == before
    assert client.post("/api/v1/funds/releases", headers=headers, json=payload).status_code == 201
    assert balances(client) == before


def test_failure_after_release_rolls_back_both_ledgers(
    release_setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.application import funds
    from app.modules.operations.contracts import InsufficientBalanceError

    client, headers, payload = release_setup
    before = balances(client)
    history_before = client.get("/api/v1/funds/history").json()

    def fail(*args: Any, **kwargs: Any) -> None:
        raise InsufficientBalanceError

    monkeypatch.setattr(funds, "post_physical_transfer", fail)
    response = client.post("/api/v1/funds/releases", headers=headers, json=payload)
    assert response.status_code == 409
    assert balances(client) == before
    assert client.get("/api/v1/funds/history").json() == history_before


def test_migration_refuses_to_discard_release_facts(release_setup: Any) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.exc import DBAPIError

    client, headers, payload = release_setup
    # Existing data survives upgrade/downgrade while the new event type is unused.
    before = balances(client)
    command.downgrade(Config("alembic.ini"), "0015_statement_imports")
    command.upgrade(Config("alembic.ini"), "head")
    assert balances(client) == before
    command.check(Config("alembic.ini"))
    assert client.post("/api/v1/funds/releases", headers=headers, json=payload).status_code == 201
    after = balances(client)
    with pytest.raises(DBAPIError, match="Cannot downgrade while fund release events exist"):
        command.downgrade(Config("alembic.ini"), "0015_statement_imports")
    assert balances(client) == after


def test_compensation_does_not_duplicate_purchase(release_setup: Any) -> None:
    client, headers, payload = release_setup
    category = client.post(
        "/api/v1/categories", headers=headers, json={"type": "expense", "name": "Purchase"}
    ).json()["id"]
    expense = client.post(
        "/api/v1/operations",
        headers=headers,
        json={
            "type": "expense",
            "account_id": payload["destination_account_id"],
            "amount": payload["amount"],
            "category_id": category,
            "occurred_on": payload["occurred_on"],
        },
    )
    assert expense.status_code == 201
    before = client.get("/api/v1/operations", params={"type": "expense"}).json()
    assert client.post("/api/v1/funds/releases", headers=headers, json=payload).status_code == 201
    after = client.get("/api/v1/operations", params={"type": "expense"}).json()
    assert after == before
    salary = next(
        a
        for a in balances(client)["accounts"]
        if a["account_id"] == payload["destination_account_id"]
    )
    assert salary["free_balance"] == "70.0000"


def test_reversal_checks_cash_and_preserves_later_explicit_allocation(release_setup: Any) -> None:
    client, headers, payload = release_setup
    result = client.post("/api/v1/funds/releases", headers=headers, json=payload)
    assert result.status_code == 201
    # A later explicit allocation is not the causal companion of this transfer,
    # even with equal date/description/amount inside the legacy matching window.
    allocation = client.post(
        "/api/v1/funds/allocations",
        headers=headers,
        json={
            "account_id": payload["destination_account_id"],
            "amount": payload["amount"],
            "occurred_on": payload["occurred_on"],
            "description": payload["description"],
            "allocations": [{"fund_id": payload["fund_id"], "amount": payload["amount"]}],
        },
    )
    assert allocation.status_code == 201
    operation_id = result.json()["operation_id"]
    assert (
        client.delete(f"/api/v1/operations/{operation_id}?version=1", headers=headers).status_code
        == 204
    )
    events = client.get("/api/v1/funds/history").json()["items"]
    assert any(event["id"] == allocation.json()["id"] for event in events)
    # Only 70 physical money remains on the destination. A second release followed
    # by spending all cash cannot be reversed; the original release stays intact.
    payload["request_id"] = str(uuid4())
    result = client.post("/api/v1/funds/releases", headers=headers, json=payload)
    assert result.status_code == 201
    category = client.post(
        "/api/v1/categories",
        headers=headers,
        json={
            "type": "expense",
            "name": "Spend free money",
        },
    ).json()["id"]
    assert (
        client.post(
            "/api/v1/operations",
            headers=headers,
            json={
                "type": "expense",
                "account_id": payload["destination_account_id"],
                "amount": "70",
                "category_id": category,
                "occurred_on": payload["occurred_on"],
            },
        ).status_code
        == 201
    )
    before = balances(client)
    response = client.delete(
        f"/api/v1/operations/{result.json()['operation_id']}?version=1", headers=headers
    )
    assert response.status_code == 409  # remaining cash is needed for the later allocation
    assert balances(client) == before
