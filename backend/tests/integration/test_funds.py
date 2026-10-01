from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Barrier
from typing import cast
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_database_engine
from app.main import create_app
from app.modules.funds import service as funds_service
from app.modules.funds.models import FundEvent, FundMovement
from app.modules.operations.models import AccountMovement, FinancialOperation

MASTER_PASSWORD = "correct-master-password"
SETUP_PAYLOAD = {
    "master_password": MASTER_PASSWORD,
    "base_currency": "RUB",
    "timezone": "Europe/Moscow",
}


def _headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("XSRF-TOKEN")
    assert token is not None
    return {"X-XSRF-TOKEN": token}


def _account(client: TestClient, headers: dict[str, str], name: str, balance: str) -> str:
    response = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"type": "debit", "name": name, "initial_balance": balance},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _fund(
    client: TestClient,
    headers: dict[str, str],
    name: str,
    percentage: str,
    target_amount: str | None = None,
) -> dict[str, object]:
    payload: dict[str, str] = {"name": name, "allocation_percentage": percentage}
    if target_amount is not None:
        payload["target_amount"] = target_amount
    response = client.post(
        "/api/v1/funds",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def test_dynamic_mode_recalculates_and_archive_restore_changes_eligibility(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        source = _account(client, headers, "Main", "500")
        destination = _account(client, headers, "Savings", "0")
        first = _fund(client, headers, "First", "10", "100")
        second = _fund(client, headers, "Second", "20", "100")

        enabled = client.put(
            "/api/v1/settings/fund-allocation-mode",
            headers=headers,
            json={"mode": "dynamic"},
        )
        assert enabled.status_code == 200
        assert enabled.json()["fund_allocation_mode"] == "dynamic"
        summary = client.get("/api/v1/funds/summary").json()
        percentages = {item["id"]: item["allocation_percentage"] for item in summary["funds"]}
        assert percentages == {first["id"]: "50.0000", second["id"]: "50.0000"}

        archived = client.post(
            f"/api/v1/funds/{second['id']}/archive",
            headers=headers,
            json={"version": second["version"]},
        )
        assert archived.status_code == 200
        summary = client.get("/api/v1/funds/summary").json()
        percentages = {item["id"]: item["allocation_percentage"] for item in summary["funds"]}
        assert percentages[first["id"]] == "100.0000"
        assert percentages[second["id"]] == "0"

        no_funds = client.post(
            f"/api/v1/funds/{first['id']}/archive",
            headers=headers,
            json={"version": first["version"]},
        )
        assert no_funds.status_code == 200
        reserved = client.post(
            "/api/v1/funds/transfer-and-allocate",
            headers=headers,
            json={
                "source_account_id": source,
                "destination_account_id": destination,
                "amount": "10",
                "occurred_on": "2026-08-17",
            },
        )
        assert reserved.status_code == 201
        assert reserved.json()["allocation"]["movements"] == []
        assert reserved.json()["allocation"]["reserve_movements"][0]["amount"] == "10.0000"
        balances = {item["id"]: item["balance"] for item in client.get("/api/v1/accounts").json()}
        assert balances[source] == "490.0000"
        assert balances[destination] == "10.0000"
        released = client.post(
            "/api/v1/funds/reserve-release",
            headers=headers,
            json={
                "account_id": destination,
                "amount": "4",
                "occurred_on": "2026-08-17",
            },
        )
        assert released.status_code == 201
        assert released.json()["type"] == "reserve_release"
        assert released.json()["reserve_movements"][0]["amount"] == "-4.0000"

        first = client.post(
            f"/api/v1/funds/{first['id']}/restore",
            headers=headers,
            json={"version": no_funds.json()["version"]},
        ).json()
        second = client.post(
            f"/api/v1/funds/{second['id']}/restore",
            headers=headers,
            json={"version": archived.json()["version"]},
        ).json()
        restored = client.get("/api/v1/funds/summary").json()
        assert restored["total_reserve"] == "0"
        assert {item["id"]: item["total_balance"] for item in restored["funds"]} == {
            first["id"]: "6.0000",
            second["id"]: "0",
        }

        direct = client.post(
            "/api/v1/funds/allocations",
            headers=headers,
            json={
                "account_id": source,
                "amount": "50",
                "occurred_on": "2026-08-17",
                "allocations": [{"fund_id": first["id"], "amount": "50"}],
            },
        )
        assert direct.status_code == 201
        after_direct = client.get("/api/v1/funds/summary").json()
        percentages = {item["id"]: item["allocation_percentage"] for item in after_direct["funds"]}
        assert percentages == {first["id"]: "32.5000", second["id"]: "67.5000"}

        distributed = client.post(
            "/api/v1/funds/transfer-and-allocate",
            headers=headers,
            json={
                "source_account_id": source,
                "destination_account_id": destination,
                "amount": "100",
                "occurred_on": "2026-08-17",
            },
        )
        assert distributed.status_code == 201
        movements = {
            item["fund_id"]: item["amount"]
            for item in distributed.json()["allocation"]["movements"]
        }
        assert movements == {first["id"]: "32.5000", second["id"]: "67.5000"}

        before_manual = client.get("/api/v1/funds/summary").json()
        before_percentages = {
            item["id"]: item["allocation_percentage"] for item in before_manual["funds"]
        }
        assert before_percentages == {first["id"]: "28.5227", second["id"]: "71.4773"}
        manual = client.put(
            "/api/v1/settings/fund-allocation-mode",
            headers=headers,
            json={"mode": "manual"},
        )
        assert manual.status_code == 200
        after_manual = client.get("/api/v1/funds/summary").json()
        assert {
            item["id"]: item["allocation_percentage"] for item in after_manual["funds"]
        } == before_percentages
        assert {
            item["id"]: item["manual_allocation_percentage"] for item in after_manual["funds"]
        } == before_percentages


def test_dynamic_distribution_uses_relative_progress_across_different_targets(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        source = _account(client, headers, "Main", "2000")
        destination = _account(client, headers, "Savings", "0")
        first = _fund(client, headers, "Small", "0", "100")
        second = _fund(client, headers, "Large", "0", "1000")

        allocated = client.post(
            "/api/v1/funds/allocations",
            headers=headers,
            json={
                "account_id": source,
                "amount": "550",
                "occurred_on": "2026-08-20",
                "allocations": [
                    {"fund_id": first["id"], "amount": "50"},
                    {"fund_id": second["id"], "amount": "500"},
                ],
            },
        )
        assert allocated.status_code == 201
        enabled = client.put(
            "/api/v1/settings/fund-allocation-mode",
            headers=headers,
            json={"mode": "dynamic"},
        )
        assert enabled.status_code == 200

        summary = client.get("/api/v1/funds/summary").json()
        percentages = {item["id"]: item["allocation_percentage"] for item in summary["funds"]}
        assert percentages == {first["id"]: "50.0000", second["id"]: "50.0000"}

        preview = client.post(
            "/api/v1/funds/allocation-preview",
            headers=headers,
            json={"account_id": source, "amount": "100"},
        )
        assert preview.status_code == 200
        assert {
            item["fund_id"]: (item["allocation_percentage"], item["amount"])
            for item in preview.json()["allocations"]
        } == {
            first["id"]: ("50.0000", "50.0000"),
            second["id"]: ("50.0000", "50.0000"),
        }

        distributed = client.post(
            "/api/v1/funds/transfer-and-allocate",
            headers=headers,
            json={
                "source_account_id": source,
                "destination_account_id": destination,
                "amount": "100",
                "occurred_on": "2026-08-20",
            },
        )
        assert distributed.status_code == 201
        assert {
            item["fund_id"]: item["amount"]
            for item in distributed.json()["allocation"]["movements"]
        } == {first["id"]: "50.0000", second["id"]: "50.0000"}

        after = client.get("/api/v1/funds/summary").json()
        percentages = {item["id"]: item["allocation_percentage"] for item in after["funds"]}
        assert percentages == {first["id"]: "0", second["id"]: "100.0000"}


def test_dynamic_mode_requires_targets_for_every_non_archived_fund(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        fund = _fund(client, headers, "Without target", "25")

        rejected = client.put(
            "/api/v1/settings/fund-allocation-mode",
            headers=headers,
            json={"mode": "dynamic"},
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"]["code"] == "dynamic_fund_targets_required"

        archived = client.post(
            f"/api/v1/funds/{fund['id']}/archive",
            headers=headers,
            json={"version": fund["version"]},
        )
        assert archived.status_code == 200
        enabled = client.put(
            "/api/v1/settings/fund-allocation-mode",
            headers=headers,
            json={"mode": "dynamic"},
        )
        assert enabled.status_code == 200
        restore = client.post(
            f"/api/v1/funds/{fund['id']}/restore",
            headers=headers,
            json={"version": archived.json()["version"]},
        )
        assert restore.status_code == 409
        assert restore.json()["detail"]["code"] == "dynamic_fund_targets_required"


def test_fund_lifecycle_allocation_and_operation_invariants(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        source = _account(client, headers, "Main", "100")
        target = _account(client, headers, "Savings", "20")
        category = client.post(
            "/api/v1/categories",
            headers=headers,
            json={"type": "expense", "name": "Food"},
        ).json()["id"]
        reserve = _fund(client, headers, "Reserve", "33.3333")
        travel = _fund(client, headers, "Travel", "20")

        over_limit = client.post(
            "/api/v1/funds",
            headers=headers,
            json={"name": "Overflow", "allocation_percentage": "46.6668"},
        )
        assert over_limit.status_code == 409
        assert over_limit.json()["detail"]["code"] == "fund_percentage_limit"

        preview = client.post(
            "/api/v1/funds/allocation-preview",
            headers=headers,
            json={"account_id": source, "amount": "10"},
        )
        assert preview.status_code == 200
        preview_body = preview.json()
        proposed = {item["fund_id"]: item["amount"] for item in preview_body["allocations"]}
        assert proposed[reserve["id"]] == "3.3333"
        assert proposed[travel["id"]] == "2.0000"
        assert preview_body["unallocated_amount"] == "4.6667"

        allocation = client.post(
            "/api/v1/funds/allocations",
            headers=headers,
            json={
                "account_id": source,
                "amount": "10",
                "occurred_on": "2026-08-11",
                "description": "Manual preview correction",
                "allocations": [
                    {"fund_id": reserve["id"], "amount": "6"},
                    {"fund_id": travel["id"], "amount": "2"},
                ],
            },
        )
        assert allocation.status_code == 201
        summary = client.get("/api/v1/funds/summary").json()
        coverage = {item["account_id"]: item for item in summary["accounts"]}
        assert coverage[source]["physical_balance"] == "100.0000"
        assert coverage[source]["reserved_balance"] == "8.0000"
        assert coverage[source]["free_balance"] == "92.0000"

        expense = client.post(
            "/api/v1/operations",
            headers=headers,
            json={
                "type": "expense",
                "occurred_on": "2026-08-11",
                "amount": "3",
                "account_id": source,
                "category_id": category,
                "fund_id": reserve["id"],
            },
        )
        assert expense.status_code == 201
        assert expense.json()["fund_amount"] == "3.0000"

        too_large_fund_expense = client.post(
            "/api/v1/operations",
            headers=headers,
            json={
                "type": "expense",
                "occurred_on": "2026-08-11",
                "amount": "4",
                "account_id": source,
                "category_id": category,
                "fund_id": reserve["id"],
            },
        )
        assert too_large_fund_expense.status_code == 409
        assert too_large_fund_expense.json()["detail"]["code"] == "insufficient_fund_balance"

        transfer = client.post(
            "/api/v1/operations",
            headers=headers,
            json={
                "type": "transfer",
                "occurred_on": "2026-08-11",
                "amount": "10",
                "account_id": source,
                "destination_account_id": target,
                "fund_id": travel["id"],
                "fund_amount": "1.5",
            },
        )
        assert transfer.status_code == 201
        travel_total = next(
            Decimal(item["total_balance"])
            for item in client.get("/api/v1/funds").json()
            if item["id"] == travel["id"]
        )
        assert travel_total == Decimal("2")
        travel_history = client.get(f"/api/v1/funds/history?fund_id={travel['id']}").json()
        assert {item["type"] for item in travel_history["items"]} == {"allocation", "transfer"}

        updated_transfer = client.put(
            f"/api/v1/operations/{transfer.json()['id']}",
            headers=headers,
            json={
                "type": "transfer",
                "occurred_on": "2026-08-11",
                "amount": "8",
                "account_id": source,
                "destination_account_id": target,
                "fund_id": travel["id"],
                "fund_amount": "1",
                "version": transfer.json()["version"],
            },
        )
        assert updated_transfer.status_code == 200
        assert updated_transfer.json()["fund_amount"] == "1.0000"
        assert (
            client.delete(
                f"/api/v1/operations/{transfer.json()['id']}?version=2", headers=headers
            ).status_code
            == 204
        )
        assert (
            next(
                item["total_balance"]
                for item in client.get("/api/v1/funds").json()
                if item["id"] == travel["id"]
            )
            == "2.0000"
        )

        redistribution = client.post(
            "/api/v1/funds/redistributions",
            headers=headers,
            json={
                "occurred_on": "2026-08-11",
                "fund_id": reserve["id"],
                "source_account_id": source,
                "destination_account_id": target,
                "amount": "1",
            },
        )
        assert redistribution.status_code == 201
        reserve_total = next(
            item["total_balance"]
            for item in client.get("/api/v1/funds").json()
            if item["id"] == reserve["id"]
        )
        assert reserve_total == "3.0000"

        updated_expense = client.put(
            f"/api/v1/operations/{expense.json()['id']}",
            headers=headers,
            json={
                "type": "expense",
                "occurred_on": "2026-08-11",
                "amount": "2",
                "account_id": source,
                "category_id": category,
                "fund_id": reserve["id"],
                "version": expense.json()["version"],
            },
        )
        assert updated_expense.status_code == 200
        assert updated_expense.json()["fund_amount"] == "2.0000"
        assert (
            client.delete(
                f"/api/v1/operations/{expense.json()['id']}?version=2", headers=headers
            ).status_code
            == 204
        )
        assert (
            next(
                item["total_balance"]
                for item in client.get("/api/v1/funds").json()
                if item["id"] == reserve["id"]
            )
            == "6.0000"
        )

        blocked_archive = client.post(
            f"/api/v1/funds/{reserve['id']}/archive",
            headers=headers,
            json={"version": reserve["version"]},
        )
        assert blocked_archive.status_code == 409
        assert blocked_archive.json()["detail"]["code"] == "fund_has_balance"
        history = client.get(f"/api/v1/funds/history?fund_id={reserve['id']}").json()
        assert history["total"] == 2


def test_transfer_to_one_fund_bypasses_percentage_distribution(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        source = _account(client, headers, "Main", "100")
        destination = _account(client, headers, "Savings", "0")
        percentage_fund = _fund(client, headers, "Reserve", "100")
        selected_fund = _fund(client, headers, "Travel", "0")

        transfer = client.post(
            "/api/v1/funds/transfer-and-allocate",
            headers=headers,
            json={
                "source_account_id": source,
                "destination_account_id": destination,
                "fund_id": selected_fund["id"],
                "amount": "30",
                "occurred_on": "2026-08-25",
            },
        )

        assert transfer.status_code == 201
        body = transfer.json()
        assert client.get(f"/api/v1/operations/{body['operation_id']}").json()["type"] == "transfer"
        assert body["allocation"]["movements"] == [
            {
                "fund_id": selected_fund["id"],
                "fund_name": "Travel",
                "account_id": destination,
                "account_name": "Savings",
                "amount": "30.0000",
            }
        ]
        summary = client.get("/api/v1/funds/summary").json()
        funds = {fund["id"]: fund for fund in summary["funds"]}
        assert funds[percentage_fund["id"]]["total_balance"] == "0"
        assert funds[selected_fund["id"]]["total_balance"] == "30.0000"
        assert funds[percentage_fund["id"]]["allocation_percentage"] == "100.0000"
        assert funds[selected_fund["id"]]["allocation_percentage"] == "0.0000"
        coverage = {account["account_id"]: account for account in summary["accounts"]}
        assert coverage[source]["physical_balance"] == "70.0000"
        assert coverage[destination]["physical_balance"] == "30.0000"
        assert coverage[destination]["fund_reserved_balance"] == "30.0000"
        assert coverage[destination]["free_balance"] == "0.0000"


def test_transfer_to_one_fund_rolls_back_when_dynamic_target_is_exceeded(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        source = _account(client, headers, "Main", "100")
        destination = _account(client, headers, "Savings", "0")
        assert (
            client.put(
                "/api/v1/settings/fund-allocation-mode",
                headers=headers,
                json={"mode": "dynamic"},
            ).status_code
            == 200
        )
        fund = _fund(client, headers, "Goal", "0", "10")

        rejected = client.post(
            "/api/v1/funds/transfer-and-allocate",
            headers=headers,
            json={
                "source_account_id": source,
                "destination_account_id": destination,
                "fund_id": fund["id"],
                "amount": "11",
                "occurred_on": "2026-08-25",
            },
        )

        assert rejected.status_code == 409
        assert rejected.json()["detail"]["code"] == "fund_target_capacity"
        balances = {item["id"]: item["balance"] for item in client.get("/api/v1/accounts").json()}
        assert balances[source] == "100.0000"
        assert balances[destination] == "0"
        summary = client.get("/api/v1/funds/summary").json()
        assert summary["total_reserved"] == "0"
        assert client.get("/api/v1/operations").json()["total"] == 1


def test_fund_target_initial_allocation_and_same_account_fund_transfer_are_atomic(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Savings", "100")
        reserve = client.post(
            "/api/v1/funds",
            headers=headers,
            json={
                "name": "Reserve",
                "allocation_percentage": "10",
                "target_amount": "80",
                "initial_account_id": account,
                "initial_amount": "30",
                "initial_occurred_on": "2026-08-14",
            },
        )
        assert reserve.status_code == 201
        assert reserve.json()["total_balance"] == "30.0000"
        assert reserve.json()["progress_percentage"] == "37.50"
        rejected_creation = client.post(
            "/api/v1/funds",
            headers=headers,
            json={
                "name": "Impossible",
                "allocation_percentage": "5",
                "initial_account_id": account,
                "initial_amount": "1000",
                "initial_occurred_on": "2026-08-14",
            },
        )
        assert rejected_creation.status_code == 409
        assert all(fund["name"] != "Impossible" for fund in client.get("/api/v1/funds").json())
        travel = _fund(client, headers, "Travel", "10")

        moved = client.post(
            "/api/v1/funds/transfers",
            headers=headers,
            json={
                "source_fund_id": reserve.json()["id"],
                "destination_fund_id": travel["id"],
                "account_id": account,
                "amount": "5",
                "occurred_on": "2026-08-14",
            },
        )
        assert moved.status_code == 201
        assert moved.json()["type"] == "fund_transfer"
        summary = client.get("/api/v1/funds/summary").json()
        assert summary["total_reserved"] == "30.0000"
        totals = {fund["id"]: fund["total_balance"] for fund in summary["funds"]}
        assert totals[reserve.json()["id"]] == "25.0000"
        assert totals[travel["id"]] == "5.0000"
        account_coverage = summary["accounts"][0]
        assert account_coverage["physical_balance"] == "100.0000"
        assert account_coverage["free_balance"] == "70.0000"

        updated_target = client.put(
            f"/api/v1/funds/{reserve.json()['id']}",
            headers=headers,
            json={
                "name": "Reserve",
                "description": None,
                "allocation_percentage": "10",
                "target_amount": "20",
                "version": reserve.json()["version"],
            },
        )
        assert updated_target.status_code == 200
        assert updated_target.json()["progress_percentage"] == "125.00"

        rejected = client.post(
            "/api/v1/funds/transfers",
            headers=headers,
            json={
                "source_fund_id": reserve.json()["id"],
                "destination_fund_id": travel["id"],
                "account_id": account,
                "amount": "100",
                "occurred_on": "2026-08-14",
            },
        )
        assert rejected.status_code == 409
        assert client.get("/api/v1/funds/summary").json()["total_reserved"] == "30.0000"


def test_operation_change_that_breaks_coverage_is_rolled_back(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Main", "100")
        fund = _fund(client, headers, "Reserve", "80")
        assert (
            client.post(
                "/api/v1/funds/allocations",
                headers=headers,
                json={
                    "account_id": account,
                    "amount": "100",
                    "occurred_on": "2026-08-11",
                    "allocations": [{"fund_id": fund["id"], "amount": "80"}],
                },
            ).status_code
            == 201
        )
        journal = client.get("/api/v1/operations").json()["items"]
        initial = next(item for item in journal if item["type"] == "balance_adjustment")

        rejected = client.delete(
            f"/api/v1/operations/{initial['id']}?version={initial['version']}", headers=headers
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"]["code"] == "insufficient_free_balance"
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "100.0000"
        assert client.get("/api/v1/funds/summary").json()["total_reserved"] == "80.0000"


def test_transfer_and_percentage_allocation_are_one_atomic_action(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        source = _account(client, headers, "Main", "100")
        target = _account(client, headers, "Savings", "10")
        reserve = _fund(client, headers, "Reserve", "25")
        travel = _fund(client, headers, "Travel", "50")

        response = client.post(
            "/api/v1/funds/transfer-and-allocate",
            headers=headers,
            json={
                "source_account_id": source,
                "destination_account_id": target,
                "amount": "20",
                "occurred_on": "2026-08-12",
                "description": "Monthly savings",
            },
        )
        assert response.status_code == 201
        body = response.json()
        operation = client.get(f"/api/v1/operations/{body['operation_id']}")
        assert operation.status_code == 200
        operation_body = operation.json()
        assert operation_body["type"] == "transfer"
        allocations = {
            movement["fund_id"]: movement["amount"] for movement in body["allocation"]["movements"]
        }
        assert allocations == {reserve["id"]: "5.0000", travel["id"]: "10.0000"}

        summary = client.get("/api/v1/funds/summary").json()
        coverage = {item["account_id"]: item for item in summary["accounts"]}
        assert coverage[source]["physical_balance"] == "80.0000"
        assert coverage[target]["physical_balance"] == "30.0000"
        assert coverage[target]["reserved_balance"] == "15.0000"
        assert coverage[target]["free_balance"] == "15.0000"

        rejected = client.post(
            "/api/v1/funds/transfer-and-allocate",
            headers=headers,
            json={
                "source_account_id": source,
                "destination_account_id": target,
                "amount": "1000",
                "occurred_on": "2026-08-12",
            },
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"]["code"] == "insufficient_balance"
        unchanged = client.get("/api/v1/funds/summary").json()
        unchanged_coverage = {item["account_id"]: item for item in unchanged["accounts"]}
        assert unchanged_coverage[source]["physical_balance"] == "80.0000"
        assert unchanged_coverage[target]["reserved_balance"] == "15.0000"

        with app.state.session_factory() as session:
            allocation = session.scalar(
                select(FundEvent).where(FundEvent.caused_by_operation_id == body["operation_id"])
            )
            assert allocation is not None

        update = client.put(
            f"/api/v1/operations/{body['operation_id']}",
            headers=headers,
            json={
                "type": "transfer",
                "occurred_on": "2026-08-12",
                "amount": "20",
                "description": "Changed savings",
                "account_id": source,
                "destination_account_id": target,
                "version": operation_body["version"],
            },
        )
        assert update.status_code == 409
        assert update.json()["detail"]["code"] == "operation_linked_to_allocation"
        assert client.get("/api/v1/funds/summary").json()["total_reserved"] == "15.0000"

        deleted = client.delete(
            f"/api/v1/operations/{body['operation_id']}?version={operation_body['version']}",
            headers=headers,
        )
        assert deleted.status_code == 204
        balances = {item["id"]: item["balance"] for item in client.get("/api/v1/accounts").json()}
        assert balances == {source: "100.0000", target: "10.0000"}
        assert client.get("/api/v1/funds/summary").json()["total_reserved"] == "0"
        with app.state.session_factory() as session:
            assert (
                session.scalar(
                    select(FundEvent).where(
                        FundEvent.caused_by_operation_id == body["operation_id"]
                    )
                )
                is None
            )


def test_deleting_legacy_unlinked_transfer_allocation_removes_its_reservation(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        source = _account(client, headers, "Main", "100")
        target = _account(client, headers, "Savings", "0")
        _fund(client, headers, "Savings", "100")
        created = client.post(
            "/api/v1/funds/transfer-and-allocate",
            headers=headers,
            json={
                "source_account_id": source,
                "destination_account_id": target,
                "amount": "20",
                "occurred_on": "2026-08-12",
                "description": "Legacy pair",
            },
        ).json()
        operation = client.get(f"/api/v1/operations/{created['operation_id']}").json()
        with app.state.session_factory() as session:
            allocation = session.scalar(
                select(FundEvent).where(FundEvent.caused_by_operation_id == created["operation_id"])
            )
            assert allocation is not None
            allocation.caused_by_operation_id = None
            session.commit()

        update = client.put(
            f"/api/v1/operations/{created['operation_id']}",
            headers=headers,
            json={
                "type": "transfer",
                "occurred_on": "2026-08-12",
                "amount": "20",
                "description": "Changed legacy pair",
                "account_id": source,
                "destination_account_id": target,
                "version": operation["version"],
            },
        )
        assert update.status_code == 409
        assert update.json()["detail"]["code"] == "operation_linked_to_allocation"

        deleted = client.delete(
            f"/api/v1/operations/{created['operation_id']}?version={operation['version']}",
            headers=headers,
        )
        assert deleted.status_code == 204
        assert client.get("/api/v1/funds/summary").json()["total_reserved"] == "0"


def test_virtual_transfer_failure_rolls_back_both_ledgers(
    postgres_database_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        source = _account(client, headers, "Source", "100")
        target = _account(client, headers, "Target", "0")
        fund = _fund(client, headers, "Reserve", "100")
        assert (
            client.post(
                "/api/v1/funds/allocations",
                headers=headers,
                json={
                    "account_id": source,
                    "amount": "20",
                    "occurred_on": "2026-08-11",
                    "allocations": [{"fund_id": fund["id"], "amount": "20"}],
                },
            ).status_code
            == 201
        )
        with app.state.session_factory() as session:
            before = (
                session.scalar(select(func.count()).select_from(FinancialOperation)),
                session.scalar(select(func.count()).select_from(AccountMovement)),
                session.scalar(select(func.count()).select_from(FundMovement)),
            )

        def add_one_then_fail(database_session: Session, movements: list[FundMovement]) -> None:
            database_session.add(movements[0])
            database_session.flush()
            raise RuntimeError("injected failure after first virtual movement")

        monkeypatch.setattr(funds_service, "_add_fund_movements", add_one_then_fail)
        with pytest.raises(RuntimeError, match="first virtual movement"):
            client.post(
                "/api/v1/operations",
                headers=headers,
                json={
                    "type": "transfer",
                    "occurred_on": "2026-08-11",
                    "amount": "5",
                    "account_id": source,
                    "destination_account_id": target,
                    "fund_id": fund["id"],
                    "fund_amount": "5",
                },
            )
        with app.state.session_factory() as session:
            after = (
                session.scalar(select(func.count()).select_from(FinancialOperation)),
                session.scalar(select(func.count()).select_from(AccountMovement)),
                session.scalar(select(func.count()).select_from(FundMovement)),
            )
        assert after == before


def test_concurrent_fund_expenses_cannot_overconsume_position(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as owner:
        assert owner.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(owner)
        account = _account(owner, headers, "Main", "100")
        fund = _fund(owner, headers, "Reserve", "100")
        category = owner.post(
            "/api/v1/categories",
            headers=headers,
            json={"type": "expense", "name": "Food"},
        ).json()["id"]
        assert (
            owner.post(
                "/api/v1/funds/allocations",
                headers=headers,
                json={
                    "account_id": account,
                    "amount": "80",
                    "occurred_on": "2026-08-11",
                    "allocations": [{"fund_id": fund["id"], "amount": "80"}],
                },
            ).status_code
            == 201
        )

    barrier = Barrier(2)

    def spend() -> int:
        with TestClient(app) as client:
            # Exercise the financial race with an already authorized session.
            client.cookies.update(owner.cookies)
            barrier.wait()
            return client.post(
                "/api/v1/operations",
                headers=_headers(client),
                json={
                    "type": "expense",
                    "occurred_on": "2026-08-11",
                    "amount": "60",
                    "account_id": account,
                    "category_id": category,
                    "fund_id": fund["id"],
                },
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: spend(), range(2)))
    assert sorted(statuses) == [201, 409]

    with TestClient(app) as client:
        assert (
            client.post("/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}).status_code
            == 200
        )
        summary = client.get("/api/v1/funds/summary").json()
        assert summary["total_reserved"] == "20.0000"
        assert summary["accounts"][0]["physical_balance"] == "40.0000"


def test_archived_fund_cannot_regain_balance_through_operation_edit(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Main", "100")
        fund = _fund(client, headers, "Reserve", "100")
        category = client.post(
            "/api/v1/categories",
            headers=headers,
            json={"type": "expense", "name": "Food"},
        ).json()["id"]
        assert (
            client.post(
                "/api/v1/funds/allocations",
                headers=headers,
                json={
                    "account_id": account,
                    "amount": "10",
                    "occurred_on": "2026-08-11",
                    "allocations": [{"fund_id": fund["id"], "amount": "10"}],
                },
            ).status_code
            == 201
        )
        expense = client.post(
            "/api/v1/operations",
            headers=headers,
            json={
                "type": "expense",
                "occurred_on": "2026-08-11",
                "amount": "10",
                "account_id": account,
                "category_id": category,
                "fund_id": fund["id"],
            },
        ).json()
        changed_definition = client.put(
            f"/api/v1/funds/{fund['id']}",
            headers=headers,
            json={
                "name": "Reserve",
                "allocation_percentage": "100",
                "version": fund["version"],
            },
        ).json()
        stale_archive = client.post(
            f"/api/v1/funds/{fund['id']}/archive",
            headers=headers,
            json={"version": fund["version"]},
        )
        assert stale_archive.status_code == 409
        assert stale_archive.json()["detail"]["code"] == "fund_conflict"
        archived = client.post(
            f"/api/v1/funds/{fund['id']}/archive",
            headers=headers,
            json={"version": changed_definition["version"]},
        )
        assert archived.status_code == 200

        changed = client.put(
            f"/api/v1/operations/{expense['id']}",
            headers=headers,
            json={
                "type": "expense",
                "occurred_on": "2026-08-11",
                "amount": "5",
                "account_id": account,
                "category_id": category,
                "fund_id": fund["id"],
                "version": expense["version"],
            },
        )
        assert changed.status_code == 409
        assert changed.json()["detail"]["code"] == "archived_fund_balance"
        operation = client.get(f"/api/v1/operations/{expense['id']}").json()
        assert operation["amount"] == "10.0000"
        assert operation["version"] == 1
        deleted = client.delete(f"/api/v1/operations/{expense['id']}?version=1", headers=headers)
        assert deleted.status_code == 409
        assert deleted.json()["detail"]["code"] == "archived_fund_balance"
        assert client.get(f"/api/v1/operations/{expense['id']}").status_code == 200


def test_dynamic_reserve_refill_is_reversed_with_expense_deletion(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Main", "100")
        assert (
            client.put(
                "/api/v1/settings/fund-allocation-mode",
                headers=headers,
                json={"mode": "dynamic"},
            ).status_code
            == 200
        )
        fund = client.post(
            "/api/v1/funds",
            headers=headers,
            json={
                "name": "Goal",
                "allocation_percentage": "0",
                "target_amount": "10",
            },
        ).json()
        assert (
            client.post(
                "/api/v1/funds/allocations",
                headers=headers,
                json={
                    "account_id": account,
                    "amount": "15",
                    "occurred_on": "2026-08-21",
                    "allocations": [{"fund_id": fund["id"], "amount": "10"}],
                },
            ).status_code
            == 201
        )
        over_target = client.post(
            "/api/v1/funds/allocations",
            headers=headers,
            json={
                "account_id": account,
                "amount": "1",
                "occurred_on": "2026-08-21",
                "allocations": [{"fund_id": fund["id"], "amount": "1"}],
            },
        )
        assert over_target.status_code == 409
        assert over_target.json()["detail"]["code"] == "fund_target_capacity"
        unchanged = client.get("/api/v1/funds/summary").json()
        assert unchanged["total_fund_reserved"] == "10.0000"
        assert unchanged["total_reserve"] == "5.0000"
        category = client.post(
            "/api/v1/categories",
            headers=headers,
            json={"type": "expense", "name": "Food"},
        ).json()["id"]
        expense = client.post(
            "/api/v1/operations",
            headers=headers,
            json={
                "type": "expense",
                "occurred_on": "2026-08-21",
                "amount": "2",
                "account_id": account,
                "category_id": category,
                "fund_id": fund["id"],
            },
        )
        assert expense.status_code == 201
        after_expense = client.get("/api/v1/funds/summary").json()
        assert after_expense["total_fund_reserved"] == "10.0000"
        assert after_expense["total_reserve"] == "3.0000"

        assert (
            client.delete(
                f"/api/v1/operations/{expense.json()['id']}?version=1", headers=headers
            ).status_code
            == 204
        )
        after_delete = client.get("/api/v1/funds/summary").json()
        assert after_delete["total_fund_reserved"] == "10.0000"
        assert after_delete["total_reserve"] == "5.0000"


def test_alpha3_database_upgrades_and_alpha4_schema_downgrades(
    postgres_database_settings: Settings,
) -> None:
    command.downgrade(Config("alembic.ini"), "0004_financial_operations")
    account = UUID("10000000-0000-0000-0000-000000000001")
    now = datetime.now(UTC)
    engine = create_database_engine(postgres_database_settings)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO accounts "
                    "(id, type, name, description, archived_at, created_at, updated_at) "
                    "VALUES (:id, CAST('debit' AS account_type), "
                    "'Legacy', NULL, NULL, :now, :now)"
                ),
                {"id": account, "now": now},
            )

        command.upgrade(Config("alembic.ini"), "head")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM funds")) == 0
            assert connection.scalar(text("SELECT count(*) FROM fund_events")) == 0
            assert connection.scalar(text("SELECT count(*) FROM fund_movements")) == 0

        command.downgrade(Config("alembic.ini"), "0004_financial_operations")
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM accounts WHERE id = :id"), {"id": account}
                )
                == 1
            )
            assert connection.scalar(text("SELECT to_regclass('public.funds')")) is None
    finally:
        engine.dispose()


def test_concurrent_allocations_cannot_overreserve_account(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as owner:
        assert owner.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(owner)
        account = _account(owner, headers, "Main", "100")
        fund = _fund(owner, headers, "Reserve", "100")

    barrier = Barrier(2)

    def allocate() -> int:
        with TestClient(app) as client:
            # Exercise the financial race with an already authorized session.
            client.cookies.update(owner.cookies)
            local_headers = _headers(client)
            barrier.wait()
            return client.post(
                "/api/v1/funds/allocations",
                headers=local_headers,
                json={
                    "account_id": account,
                    "amount": "80",
                    "occurred_on": "2026-08-11",
                    "allocations": [{"fund_id": fund["id"], "amount": "80"}],
                },
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: allocate(), range(2)))
    assert sorted(statuses) == [201, 409]

    with TestClient(app) as client:
        assert (
            client.post("/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}).status_code
            == 200
        )
        summary = client.get("/api/v1/funds/summary").json()
        assert summary["total_reserved"] == "80.0000"
        assert summary["total_free"] == "20.0000"


def test_concurrent_fund_definitions_cannot_exceed_percentage_limit(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as owner:
        assert owner.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201

    barrier = Barrier(2)

    def create(name: str) -> int:
        with TestClient(app) as client:
            # Exercise the financial race with an already authorized session.
            client.cookies.update(owner.cookies)
            barrier.wait()
            return client.post(
                "/api/v1/funds",
                headers=_headers(client),
                json={"name": name, "allocation_percentage": "60"},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(create, ["First", "Second"]))
    assert sorted(statuses) == [201, 409]

    with TestClient(app) as client:
        assert (
            client.post("/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}).status_code
            == 200
        )
        assert client.get("/api/v1/funds/summary").json()["active_percentage"] == "60.0000"
