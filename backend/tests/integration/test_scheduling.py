from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier, Event
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.config import Settings
from app.main import create_app
from app.modules.funds.models import FundMovement
from app.modules.operations.models import AccountMovement, FinancialOperation
from app.modules.scheduling import service as scheduling_service
from app.modules.scheduling.models import ExpectedOccurrence, RecurrenceFrequency, RecurringRule
from app.modules.scheduling.service import (
    calendar_year_later,
    list_occurrence_responses,
    materialize_all,
)

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


def _category(client: TestClient, headers: dict[str, str], name: str, category_type: str) -> str:
    response = client.post(
        "/api/v1/categories",
        headers=headers,
        json={"type": category_type, "name": name},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _horizon_today(client: TestClient, headers: dict[str, str]) -> date:
    response = client.post("/api/v1/scheduling/materialize", headers=headers)
    assert response.status_code == 200
    return date.fromisoformat(response.json()["horizon_from"])


def _rule_payload(
    *,
    operation_type: str,
    start_on: date,
    end_on: date | None,
    amount: str,
    account_id: str,
    category_id: str | None = None,
    destination_account_id: str | None = None,
) -> dict[str, object]:
    return {
        "type": operation_type,
        "frequency": "daily",
        "start_on": start_on.isoformat(),
        "end_on": end_on.isoformat() if end_on else None,
        "amount": amount,
        "description": f"Scheduled {operation_type}",
        "account_id": account_id,
        "destination_account_id": destination_account_id,
        "category_id": category_id,
    }


def _occurrences(client: TestClient, rule_id: str) -> list[dict[str, object]]:
    response = client.get("/api/v1/scheduling/occurrences?page_size=367")
    assert response.status_code == 200
    return [item for item in response.json()["items"] if item["rule_id"] == rule_id]


def test_expected_occurrence_lifecycle_posts_only_on_confirmation(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.get("/api/v1/scheduling/rules").status_code == 401
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        assert client.post("/api/v1/scheduling/materialize").status_code == 403
        headers = _headers(client)
        source = _account(client, headers, "Main", "100")
        destination = _account(client, headers, "Savings", "0")
        income_category = _category(client, headers, "Salary", "income")
        expense_category = _category(client, headers, "Food", "expense")
        today = _horizon_today(client, headers)

        income_response = client.post(
            "/api/v1/scheduling/rules",
            headers=headers,
            json=_rule_payload(
                operation_type="income",
                start_on=today,
                end_on=today + timedelta(days=2),
                amount="10",
                account_id=source,
                category_id=income_category,
            ),
        )
        assert income_response.status_code == 201
        income_rule = income_response.json()
        income_occurrences = _occurrences(client, income_rule["id"])
        assert len(income_occurrences) == 3
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "100.0000"

        with app.state.session_factory.begin() as session:
            materialize_all(session, today=today + timedelta(days=1))
            overdue_page = list_occurrence_responses(
                session,
                page=1,
                page_size=10,
                due_from=None,
                due_to=today,
                account_id=None,
                operation_type=None,
                statuses=None,
                today=today + timedelta(days=1),
            )
            assert overdue_page.items[0].status == "pending"
            assert overdue_page.items[0].overdue is True

        first = income_occurrences[0]
        confirmed = client.post(
            f"/api/v1/scheduling/occurrences/{first['id']}/confirm",
            headers=headers,
            json={"version": first["version"]},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "confirmed"
        operation_id = confirmed.json()["actual_operation_id"]
        assert operation_id is not None
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "110.0000"

        repeated = client.post(
            f"/api/v1/scheduling/occurrences/{first['id']}/confirm",
            headers=headers,
            json={"version": first["version"]},
        )
        assert repeated.status_code == 200
        assert repeated.json()["actual_operation_id"] == operation_id
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "110.0000"

        linked_operation = client.get(f"/api/v1/operations/{operation_id}").json()
        blocked_delete = client.delete(
            f"/api/v1/operations/{operation_id}?version={linked_operation['version']}",
            headers=headers,
        )
        assert blocked_delete.status_code == 409
        assert blocked_delete.json()["detail"]["code"] == "operation_linked_to_occurrence"

        second = income_occurrences[1]
        postponed_date = date.fromisoformat(str(second["due_on"])) + timedelta(days=5)
        postponed = client.post(
            f"/api/v1/scheduling/occurrences/{second['id']}/postpone",
            headers=headers,
            json={"version": second["version"], "due_on": postponed_date.isoformat()},
        )
        assert postponed.status_code == 200
        assert postponed.json()["status"] == "postponed"
        assert postponed.json()["due_on"] == postponed_date.isoformat()
        assert client.get("/api/v1/scheduling/rules").json()[0]["start_on"] == today.isoformat()

        third = income_occurrences[2]
        cancelled = client.post(
            f"/api/v1/scheduling/occurrences/{third['id']}/cancel",
            headers=headers,
            json={"version": third["version"]},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "110.0000"

        expense_rule = client.post(
            "/api/v1/scheduling/rules",
            headers=headers,
            json=_rule_payload(
                operation_type="expense",
                start_on=today,
                end_on=today,
                amount="200",
                account_id=source,
                category_id=expense_category,
            ),
        ).json()
        expense_occurrence = _occurrences(client, expense_rule["id"])[0]
        rejected = client.post(
            f"/api/v1/scheduling/occurrences/{expense_occurrence['id']}/confirm",
            headers=headers,
            json={"version": expense_occurrence["version"]},
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"]["code"] == "insufficient_balance"
        unchanged = _occurrences(client, expense_rule["id"])[0]
        assert unchanged["status"] == "pending"
        assert unchanged["actual_operation_id"] is None

        transfer_rule = client.post(
            "/api/v1/scheduling/rules",
            headers=headers,
            json=_rule_payload(
                operation_type="transfer",
                start_on=today,
                end_on=today,
                amount="5",
                account_id=source,
                destination_account_id=destination,
            ),
        ).json()
        transfer_occurrence = _occurrences(client, transfer_rule["id"])[0]
        assert (
            client.post(
                f"/api/v1/scheduling/occurrences/{transfer_occurrence['id']}/confirm",
                headers=headers,
                json={"version": transfer_occurrence["version"]},
            ).status_code
            == 200
        )
        balances = {item["id"]: item["balance"] for item in client.get("/api/v1/accounts").json()}
        assert balances[source] == "105.0000"
        assert balances[destination] == "5.0000"


def test_future_recurring_occurrence_can_be_edited_and_confirmed_today(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        original_account = _account(client, headers, "Original", "0")
        accepted_account = _account(client, headers, "Accepted", "0")
        original_category = _category(client, headers, "Salary", "income")
        accepted_category = _category(client, headers, "Bonus", "income")
        today = _horizon_today(client, headers)
        planned_on = today + timedelta(days=10)
        rule = client.post(
            "/api/v1/scheduling/rules",
            headers=headers,
            json=_rule_payload(
                operation_type="income",
                start_on=planned_on,
                end_on=planned_on + timedelta(days=1),
                amount="10",
                account_id=original_account,
                category_id=original_category,
            ),
        ).json()
        occurrences = _occurrences(client, rule["id"])
        selected, sibling = occurrences

        confirmed = client.post(
            f"/api/v1/scheduling/occurrences/{selected['id']}/confirm",
            headers=headers,
            json={
                "version": selected["version"],
                "operation": {
                    "type": "income",
                    "amount": "25.50",
                    "description": "Accepted early",
                    "account_id": accepted_account,
                    "destination_account_id": None,
                    "category_id": accepted_category,
                    "allocate_to_funds": False,
                },
            },
        )

        assert confirmed.status_code == 200
        snapshot = confirmed.json()
        assert snapshot["status"] == "confirmed"
        assert snapshot["due_on"] == planned_on.isoformat()
        assert snapshot["amount"] == "25.5000"
        assert snapshot["description"] == "Accepted early"
        assert snapshot["account_id"] == accepted_account
        assert snapshot["category_id"] == accepted_category
        assert snapshot["manually_modified"] is True
        operation_id = snapshot["actual_operation_id"]
        operation = client.get(f"/api/v1/operations/{operation_id}").json()
        assert operation["occurred_on"] == today.isoformat()
        assert operation["amount"] == "25.5000"
        assert operation["description"] == "Accepted early"
        assert operation["account_id"] == accepted_account
        assert operation["category_id"] == accepted_category

        balances = {item["id"]: item["balance"] for item in client.get("/api/v1/accounts").json()}
        assert isinstance(balances[original_account], str)
        assert Decimal(balances[original_account]) == Decimal("0")
        assert balances[accepted_account] == "25.5000"
        persisted_rule = client.get("/api/v1/scheduling/rules").json()[0]
        assert persisted_rule["amount"] == "10.0000"
        assert persisted_rule["account_id"] == original_account
        persisted_sibling = client.get(f"/api/v1/scheduling/occurrences/{sibling['id']}").json()
        assert persisted_sibling["amount"] == "10.0000"
        assert persisted_sibling["account_id"] == original_account

        repeated = client.post(
            f"/api/v1/scheduling/occurrences/{selected['id']}/confirm",
            headers=headers,
            json={"version": selected["version"]},
        )
        assert repeated.status_code == 200
        assert repeated.json()["actual_operation_id"] == operation_id


def test_postponing_with_series_shift_preserves_manual_and_confirmed_occurrences(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Main", "100")
        category = _category(client, headers, "Salary", "income")
        today = _horizon_today(client, headers)
        payload = _rule_payload(
            operation_type="income",
            start_on=today,
            end_on=today + timedelta(days=4),
            amount="10",
            account_id=account,
            category_id=category,
        )
        created = client.post("/api/v1/scheduling/rules", headers=headers, json=payload).json()
        occurrences = _occurrences(client, created["id"])

        manually_postponed = occurrences[2]
        manual_due_on = date.fromisoformat(str(manually_postponed["due_on"])) + timedelta(days=2)
        assert (
            client.post(
                f"/api/v1/scheduling/occurrences/{manually_postponed['id']}/postpone",
                headers=headers,
                json={
                    "version": manually_postponed["version"],
                    "rule_version": created["version"] + 100,
                    "due_on": manual_due_on.isoformat(),
                },
            ).status_code
            == 200
        )
        confirmed = occurrences[3]
        assert (
            client.post(
                f"/api/v1/scheduling/occurrences/{confirmed['id']}/confirm",
                headers=headers,
                json={"version": confirmed["version"]},
            ).status_code
            == 200
        )

        update_payload = {**payload, "active": True, "version": created["version"]}
        update_payload["shift_future_on_postpone"] = True
        update_payload["end_on"] = (today + timedelta(days=3)).isoformat()
        updated_rule = client.put(
            f"/api/v1/scheduling/rules/{created['id']}", headers=headers, json=update_payload
        ).json()
        before = {item["scheduled_on"]: item for item in _occurrences(client, created["id"])}
        first = before[today.isoformat()]
        missing_rule_version = client.post(
            f"/api/v1/scheduling/occurrences/{first['id']}/postpone",
            headers=headers,
            json={
                "version": first["version"],
                "due_on": (today + timedelta(days=4)).isoformat(),
            },
        )
        assert missing_rule_version.status_code == 409
        assert missing_rule_version.json()["detail"]["code"] == "scheduling_conflict"
        stale = client.post(
            f"/api/v1/scheduling/occurrences/{first['id']}/postpone",
            headers=headers,
            json={
                "version": first["version"],
                "rule_version": created["version"],
                "due_on": (today + timedelta(days=4)).isoformat(),
            },
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "scheduling_conflict"
        response = client.post(
            f"/api/v1/scheduling/occurrences/{first['id']}/postpone",
            headers=headers,
            json={
                "version": first["version"],
                "rule_version": updated_rule["version"],
                "due_on": (today + timedelta(days=4)).isoformat(),
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["series_shift_applied"] is True
        assert result["shift_days"] == 4
        assert result["shifted_occurrences"] == 1
        assert result["preserved_occurrences"] == 3

        after = {item["scheduled_on"]: item for item in _occurrences(client, created["id"])}
        assert (
            after[(today + timedelta(days=1)).isoformat()]["due_on"]
            == (today + timedelta(days=5)).isoformat()
        )
        assert after[(today + timedelta(days=2)).isoformat()]["due_on"] == manual_due_on.isoformat()
        assert after[(today + timedelta(days=3)).isoformat()]["status"] == "confirmed"
        cancelled = after[(today + timedelta(days=4)).isoformat()]
        assert cancelled["status"] == "cancelled"
        assert cancelled["due_on"] == (today + timedelta(days=4)).isoformat()
        assert cancelled["series_shift_days"] == 0
        assert cancelled["preserve_from_series_shift"] is True
        cancelled_before = before[(today + timedelta(days=4)).isoformat()]
        cancelled_version_before = cancelled_before["version"]
        assert isinstance(cancelled_version_before, int)
        assert cancelled["version"] == cancelled_version_before + 1
        rule_after = client.get("/api/v1/scheduling/rules").json()[0]
        assert rule_after["series_shift_days"] == 4

        extended_payload = {
            **payload,
            "active": True,
            "version": result["rule_version"],
            "shift_future_on_postpone": True,
            "end_on": (today + timedelta(days=8)).isoformat(),
        }
        extended = client.put(
            f"/api/v1/scheduling/rules/{created['id']}", headers=headers, json=extended_payload
        )
        assert extended.status_code == 200
        rematerialized = {
            item["scheduled_on"]: item for item in _occurrences(client, created["id"])
        }
        assert rematerialized[(today + timedelta(days=4)).isoformat()]["status"] == "cancelled"
        assert (
            rematerialized[(today + timedelta(days=4)).isoformat()]["preserve_from_series_shift"]
            is True
        )
        assert (
            rematerialized[(today + timedelta(days=5)).isoformat()]["due_on"]
            == (today + timedelta(days=9)).isoformat()
        )

    with pytest.raises(IntegrityError), app.state.session_factory.begin() as session:
        session.execute(
            update(ExpectedOccurrence)
            .where(ExpectedOccurrence.id == cancelled["id"])
            .values(manually_modified=True)
        )


def test_disabling_shifted_rule_cancels_materialized_events_beyond_current_horizon(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Boundary", "0")
        category = _category(client, headers, "Salary", "income")
        today = _horizon_today(client, headers)
        horizon_to = calendar_year_later(today)
        payload = _rule_payload(
            operation_type="income",
            start_on=today,
            end_on=horizon_to,
            amount="10",
            account_id=account,
            category_id=category,
        )
        payload["shift_future_on_postpone"] = True
        rule = client.post("/api/v1/scheduling/rules", headers=headers, json=payload).json()
        occurrences = _occurrences(client, rule["id"])
        first = occurrences[0]
        shifted = client.post(
            f"/api/v1/scheduling/occurrences/{first['id']}/postpone",
            headers=headers,
            json={
                "version": first["version"],
                "rule_version": rule["version"],
                "due_on": (today + timedelta(days=4)).isoformat(),
            },
        ).json()
        boundary_before = next(
            item
            for item in _occurrences(client, rule["id"])
            if item["scheduled_on"] == horizon_to.isoformat()
        )
        assert boundary_before["due_on"] == (horizon_to + timedelta(days=4)).isoformat()

        disabled_payload = {
            **payload,
            "active": False,
            "version": shifted["rule_version"],
        }
        disabled = client.put(
            f"/api/v1/scheduling/rules/{rule['id']}", headers=headers, json=disabled_payload
        )
        assert disabled.status_code == 200
        boundary_after = next(
            item for item in _occurrences(client, rule["id"]) if item["id"] == boundary_before["id"]
        )
        assert boundary_after["status"] == "cancelled"


def test_series_shift_calendar_overflow_rolls_back_rule_and_occurrences(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Rollback", "0")
        category = _category(client, headers, "Salary", "income")
        today = _horizon_today(client, headers)
        payload = _rule_payload(
            operation_type="income",
            start_on=today,
            end_on=today + timedelta(days=1),
            amount="10",
            account_id=account,
            category_id=category,
        )
        payload["shift_future_on_postpone"] = True
        rule = client.post("/api/v1/scheduling/rules", headers=headers, json=payload).json()
        before = _occurrences(client, rule["id"])

        rejected = client.post(
            f"/api/v1/scheduling/occurrences/{before[0]['id']}/postpone",
            headers=headers,
            json={
                "version": before[0]["version"],
                "rule_version": rule["version"],
                "due_on": date.max.isoformat(),
            },
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"]["code"] == "invalid_occurrence_transition"
        rule_after = client.get("/api/v1/scheduling/rules").json()[0]
        assert rule_after["version"] == rule["version"]
        assert rule_after["series_shift_days"] == 0
        assert _occurrences(client, rule["id"]) == before


def test_series_shift_locks_only_selected_and_mutable_future_occurrences(
    postgres_database_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Narrow locks", "0")
        category = _category(client, headers, "Salary", "income")
        today = _horizon_today(client, headers)
        payload = _rule_payload(
            operation_type="income",
            start_on=today,
            end_on=today + timedelta(days=4),
            amount="10",
            account_id=account,
            category_id=category,
        )
        rule = client.post("/api/v1/scheduling/rules", headers=headers, json=payload).json()
        with app.state.session_factory() as session:
            assert (
                session.scalar(
                    select(func.to_regclass("ix_expected_occurrences_series_shift_candidates"))
                )
                == "ix_expected_occurrences_series_shift_candidates"
            )
        occurrences = _occurrences(client, rule["id"])
        manual_due_on = date.fromisoformat(str(occurrences[4]["due_on"])) + timedelta(days=1)
        assert (
            client.post(
                f"/api/v1/scheduling/occurrences/{occurrences[4]['id']}/postpone",
                headers=headers,
                json={"version": occurrences[4]["version"], "due_on": manual_due_on.isoformat()},
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/scheduling/occurrences/{occurrences[3]['id']}/confirm",
                headers=headers,
                json={"version": occurrences[3]["version"]},
            ).status_code
            == 200
        )
        enabled_payload = {
            **payload,
            "active": True,
            "version": rule["version"],
            "shift_future_on_postpone": True,
        }
        enabled = client.put(
            f"/api/v1/scheduling/rules/{rule['id']}", headers=headers, json=enabled_payload
        ).json()
        current = {item["id"]: item for item in _occurrences(client, rule["id"])}

    locks_acquired = Event()
    allow_materialization = Event()
    original_materialize = scheduling_service._materialize_missing_occurrences

    def pause_after_candidate_locks(*args: Any, **kwargs: Any) -> int:
        locks_acquired.set()
        if not allow_materialization.wait(timeout=10):
            raise TimeoutError("series-shift lock test was not released")
        return original_materialize(*args, **kwargs)

    monkeypatch.setattr(
        scheduling_service,
        "_materialize_missing_occurrences",
        pause_after_candidate_locks,
    )

    def shift_series() -> int:
        with TestClient(app) as concurrent_client:
            assert (
                concurrent_client.post(
                    "/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}
                ).status_code
                == 200
            )
            selected = current[occurrences[1]["id"]]
            return concurrent_client.post(
                f"/api/v1/scheduling/occurrences/{selected['id']}/postpone",
                headers=_headers(concurrent_client),
                json={
                    "version": selected["version"],
                    "rule_version": enabled["version"],
                    "due_on": (
                        date.fromisoformat(str(selected["due_on"])) + timedelta(days=2)
                    ).isoformat(),
                },
            ).status_code

    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(shift_series)
        try:
            assert locks_acquired.wait(timeout=10), "series shift did not acquire candidate locks"
            excluded_ids = [occurrences[0]["id"], occurrences[3]["id"], occurrences[4]["id"]]
            with app.state.session_factory.begin() as session:
                unlocked = session.scalars(
                    select(ExpectedOccurrence)
                    .where(ExpectedOccurrence.id.in_(excluded_ids))
                    .order_by(ExpectedOccurrence.id)
                    .with_for_update(nowait=True)
                ).all()
                assert len(unlocked) == 3
            with pytest.raises(OperationalError), app.state.session_factory.begin() as session:
                session.scalar(
                    select(ExpectedOccurrence)
                    .where(ExpectedOccurrence.id == occurrences[2]["id"])
                    .with_for_update(nowait=True)
                )
        finally:
            allow_materialization.set()
        assert result.result(timeout=10) == 200


def test_rule_edit_protects_manual_occurrences_and_materialization_is_idempotent(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Empty", "0")
        category = _category(client, headers, "Salary", "income")
        today = _horizon_today(client, headers)
        original = _rule_payload(
            operation_type="income",
            start_on=today + timedelta(days=1),
            end_on=today + timedelta(days=4),
            amount="10",
            account_id=account,
            category_id=category,
        )
        created = client.post("/api/v1/scheduling/rules", headers=headers, json=original).json()
        timezone_change = client.put(
            "/api/v1/settings",
            headers=headers,
            json={"base_currency": "RUB", "timezone": "UTC"},
        )
        assert timezone_change.status_code == 409
        assert timezone_change.json()["detail"]["code"] == "timezone_locked_by_schedule"
        before = _occurrences(client, created["id"])
        assert len(before) == 4
        first = before[0]
        manual_due = today + timedelta(days=8)
        assert (
            client.post(
                f"/api/v1/scheduling/occurrences/{first['id']}/postpone",
                headers=headers,
                json={"version": first["version"], "due_on": manual_due.isoformat()},
            ).status_code
            == 200
        )

        replacement = _rule_payload(
            operation_type="income",
            start_on=today + timedelta(days=2),
            end_on=today + timedelta(days=3),
            amount="20",
            account_id=account,
            category_id=category,
        )
        replacement.update({"active": True, "version": created["version"]})
        updated = client.put(
            f"/api/v1/scheduling/rules/{created['id']}", headers=headers, json=replacement
        )
        assert updated.status_code == 200
        after = {item["scheduled_on"]: item for item in _occurrences(client, created["id"])}
        protected = after[(today + timedelta(days=1)).isoformat()]
        assert protected["status"] == "postponed"
        assert protected["due_on"] == manual_due.isoformat()
        assert protected["amount"] == "10.0000"
        for offset in (2, 3):
            item = after[(today + timedelta(days=offset)).isoformat()]
            assert item["status"] == "pending"
            assert item["amount"] == "20.0000"
        automatic_cancel = after[(today + timedelta(days=4)).isoformat()]
        assert automatic_cancel["status"] == "cancelled"
        assert automatic_cancel["manually_modified"] is False

        disabled_payload = dict(replacement)
        disabled_payload.update({"active": False, "version": updated.json()["version"]})
        disabled = client.put(
            f"/api/v1/scheduling/rules/{created['id']}",
            headers=headers,
            json=disabled_payload,
        )
        assert disabled.status_code == 200
        disabled_items = _occurrences(client, created["id"])
        assert next(item for item in disabled_items if item["id"] == first["id"])["status"] == (
            "postponed"
        )
        assert all(
            item["status"] == "cancelled" for item in disabled_items if item["id"] != first["id"]
        )

        enabled_payload = dict(replacement)
        enabled_payload.update({"active": True, "version": disabled.json()["version"]})
        assert (
            client.put(
                f"/api/v1/scheduling/rules/{created['id']}",
                headers=headers,
                json=enabled_payload,
            ).status_code
            == 200
        )
        restored = {item["scheduled_on"]: item for item in _occurrences(client, created["id"])}
        assert restored[(today + timedelta(days=2)).isoformat()]["status"] == "pending"
        assert restored[(today + timedelta(days=3)).isoformat()]["status"] == "pending"
        assert restored[(today + timedelta(days=1)).isoformat()]["status"] == "postponed"

        first_retry = client.post("/api/v1/scheduling/materialize", headers=headers).json()
        second_retry = client.post("/api/v1/scheduling/materialize", headers=headers).json()
        assert first_retry["created"] == second_retry["created"] == 0
        assert second_retry["updated"] == second_retry["cancelled"] == 0

        blocked_delete = client.delete(f"/api/v1/accounts/{account}", headers=headers)
        assert blocked_delete.status_code == 409
        type_change = client.put(
            f"/api/v1/categories/{category}",
            headers=headers,
            json={"type": "expense", "name": "Salary"},
        )
        assert type_change.status_code == 409
        assert type_change.json()["detail"]["code"] == "category_type_has_history"

    barrier = Barrier(2)

    def materialize_concurrently() -> int:
        with TestClient(app) as concurrent_client:
            assert (
                concurrent_client.post(
                    "/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}
                ).status_code
                == 200
            )
            barrier.wait()
            return concurrent_client.post(
                "/api/v1/scheduling/materialize", headers=_headers(concurrent_client)
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: materialize_concurrently(), range(2)))
    assert statuses == [200, 200]
    with app.state.session_factory() as session:
        count = session.scalar(select(func.count()).select_from(ExpectedOccurrence))
        unique_count = session.scalar(
            select(func.count()).select_from(
                select(ExpectedOccurrence.rule_id, ExpectedOccurrence.scheduled_on)
                .distinct()
                .subquery()
            )
        )
        assert count == unique_count


def test_open_ended_rules_roll_forward_and_confirmation_can_override_amount(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Income", "0")
        category = _category(client, headers, "Salary", "income")
        today = _horizon_today(client, headers)
        rule = client.post(
            "/api/v1/scheduling/rules",
            headers=headers,
            json=_rule_payload(
                operation_type="income",
                start_on=today,
                end_on=None,
                amount="10",
                account_id=account,
                category_id=category,
            ),
        ).json()
        occurrence = _occurrences(client, rule["id"])[0]
        confirmed = client.post(
            f"/api/v1/scheduling/occurrences/{occurrence['id']}/confirm",
            headers=headers,
            json={"version": occurrence["version"], "amount": "12.34"},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["amount"] == "12.3400"
        assert confirmed.json()["manually_modified"] is True
        actual_operation_id = confirmed.json()["actual_operation_id"]

        replacement = _rule_payload(
            operation_type="income",
            start_on=today,
            end_on=None,
            amount="20",
            account_id=account,
            category_id=category,
        )
        replacement.update({"active": True, "version": rule["version"]})
        updated = client.put(
            f"/api/v1/scheduling/rules/{rule['id']}", headers=headers, json=replacement
        )
        assert updated.status_code == 200
        items = _occurrences(client, rule["id"])
        assert next(item for item in items if item["id"] == occurrence["id"])["amount"] == "12.3400"
        assert next(item for item in items if item["id"] != occurrence["id"])["amount"] == "20.0000"

        actual = client.get(f"/api/v1/operations/{actual_operation_id}")
        assert actual.status_code == 200
        assert actual.json()["amount"] == "12.3400"

    with app.state.session_factory.begin() as session:
        original_last = session.scalar(
            select(func.max(ExpectedOccurrence.scheduled_on)).where(
                ExpectedOccurrence.rule_id == rule["id"]
            )
        )
        assert original_last is not None
        materialize_all(session, today=today + timedelta(days=370))
        rolled_last = session.scalar(
            select(func.max(ExpectedOccurrence.scheduled_on)).where(
                ExpectedOccurrence.rule_id == rule["id"]
            )
        )
        assert rolled_last is not None and rolled_last > original_last


def test_scheduled_transfer_and_percentage_allocation_are_atomic(
    postgres_database_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        source = _account(client, headers, "Source", "100")
        destination = _account(client, headers, "Destination", "0")
        today = _horizon_today(client, headers)
        payload = _rule_payload(
            operation_type="transfer",
            start_on=today,
            end_on=today,
            amount="20",
            account_id=source,
            destination_account_id=destination,
        )
        payload["allocate_to_funds"] = True
        rule = client.post("/api/v1/scheduling/rules", headers=headers, json=payload)
        assert rule.status_code == 201
        assert rule.json()["allocate_to_funds"] is True
        occurrence = _occurrences(client, rule.json()["id"])[0]
        assert occurrence["allocate_to_funds"] is True

        unavailable = client.post(
            f"/api/v1/scheduling/occurrences/{occurrence['id']}/confirm",
            headers=headers,
            json={"version": occurrence["version"], "amount": "24"},
        )
        assert unavailable.status_code == 409
        assert unavailable.json()["detail"]["code"] == "fund_allocation_unavailable"
        unchanged_balances = {
            item["id"]: item["balance"] for item in client.get("/api/v1/accounts").json()
        }
        assert unchanged_balances[source] == "100.0000"
        assert Decimal(str(unchanged_balances[destination])) == 0

        fund = client.post(
            "/api/v1/funds",
            headers=headers,
            json={"name": "Reserve", "allocation_percentage": "25"},
        )
        assert fund.status_code == 201
        fund_forecast = client.get("/api/v1/forecast/funds?horizon=two_weeks")
        assert fund_forecast.status_code == 200
        assert fund_forecast.json()["planned_transfer_total"] == "20.0000"
        assert fund_forecast.json()["planned_allocation_total"] == "5.0000"
        assert fund_forecast.json()["series"][0]["ending_balance"] == "5.0000"
        confirmed = client.post(
            f"/api/v1/scheduling/occurrences/{occurrence['id']}/confirm",
            headers=headers,
            json={"version": occurrence["version"], "amount": "24"},
        )
        assert confirmed.status_code == 200
        confirmed_forecast = client.get("/api/v1/forecast/funds?horizon=two_weeks")
        assert Decimal(confirmed_forecast.json()["planned_transfer_total"]) == 0
        assert confirmed_forecast.json()["series"][0]["starting_balance"] == "6.0000"
        balances = {item["id"]: item["balance"] for item in client.get("/api/v1/accounts").json()}
        assert balances[source] == "76.0000"
        assert balances[destination] == "24.0000"
        exported = client.get("/api/v1/backup/export")
        assert exported.status_code == 200
        exported_rule = next(
            item
            for item in exported.json()["data"]["recurring_rules"]
            if item["id"] == rule.json()["id"]
        )
        exported_occurrence = next(
            item
            for item in exported.json()["data"]["expected_occurrences"]
            if item["id"] == occurrence["id"]
        )
        assert exported_rule["allocate_to_funds"] is True
        assert exported_occurrence["allocate_to_funds"] is True

        rollback_rule = client.post(
            "/api/v1/scheduling/rules", headers=headers, json=payload
        ).json()
        rollback_occurrence = _occurrences(client, rollback_rule["id"])[0]

        def fail_after_financial_effects(
            expected: ExpectedOccurrence, operation_id: object
        ) -> None:
            assert expected.id is not None
            assert operation_id is not None
            raise RuntimeError("injected failure after transfer and allocation")

        monkeypatch.setattr(
            scheduling_service, "_link_confirmed_operation", fail_after_financial_effects
        )
        with pytest.raises(RuntimeError, match="after transfer and allocation"):
            client.post(
                f"/api/v1/scheduling/occurrences/{rollback_occurrence['id']}/confirm",
                headers=headers,
                json={"version": rollback_occurrence["version"]},
            )

        rolled_back_balances = {
            item["id"]: item["balance"] for item in client.get("/api/v1/accounts").json()
        }
        assert rolled_back_balances == balances
        persisted = _occurrences(client, rollback_rule["id"])[0]
        assert persisted["status"] == "pending"
        assert persisted["actual_operation_id"] is None

    with app.state.session_factory() as session:
        movements = session.scalars(select(FundMovement)).all()
        assert len(movements) == 1
        assert str(movements[0].account_id) == destination
        assert movements[0].amount == 6


def test_one_off_plan_stays_unposted_until_application_today_confirmation(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Main", "100")
        category = _category(client, headers, "Insurance", "expense")
        today = _horizon_today(client, headers)
        planned_on = today + timedelta(days=10)

        created = client.post(
            "/api/v1/scheduling/one-off-plans",
            headers=headers,
            json={
                "type": "expense",
                "scheduled_on": planned_on.isoformat(),
                "amount": "20",
                "description": "Insurance",
                "account_id": account,
                "category_id": category,
            },
        )
        assert created.status_code == 201
        plan = created.json()
        assert plan["source_kind"] == "one_off"
        assert plan["rule_id"] is None
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "100.0000"
        assert client.get("/api/v1/operations").json()["total"] == 1
        forecast = client.get("/api/v1/forecast?horizon=two_weeks").json()
        assert forecast["ending_balance"] == "80.0000"

        edited = client.put(
            f"/api/v1/scheduling/one-off-plans/{plan['id']}",
            headers=headers,
            json={
                "type": "expense",
                "scheduled_on": (today - timedelta(days=1)).isoformat(),
                "amount": "25",
                "description": "Updated insurance",
                "account_id": account,
                "category_id": category,
                "version": plan["version"],
            },
        )
        assert edited.status_code == 200
        assert edited.json()["status"] == "pending"
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "100.0000"

        confirmed = client.post(
            f"/api/v1/scheduling/occurrences/{plan['id']}/confirm",
            headers=headers,
            json={"version": edited.json()["version"]},
        )
        assert confirmed.status_code == 200
        operation_id = confirmed.json()["actual_operation_id"]
        assert operation_id is not None
        operation = client.get(f"/api/v1/operations/{operation_id}").json()
        assert operation["occurred_on"] == today.isoformat()
        assert client.get("/api/v1/accounts").json()[0]["balance"] == "75.0000"
        repeated = client.post(
            f"/api/v1/scheduling/occurrences/{plan['id']}/confirm",
            headers=headers,
            json={"version": plan["version"]},
        )
        assert repeated.status_code == 200
        assert repeated.json()["actual_operation_id"] == operation_id

        future_fact = client.post(
            "/api/v1/operations",
            headers=headers,
            json={
                "type": "expense",
                "occurred_on": planned_on.isoformat(),
                "amount": "1",
                "account_id": account,
                "category_id": category,
            },
        )
        assert future_fact.status_code == 422
        assert future_fact.json()["detail"]["code"] == "future_operation_requires_plan"

    with pytest.raises(RuntimeError, match="one-off plans exist"):
        command.downgrade(Config("alembic.ini"), "0013_fund_reserve")


def test_concurrent_confirmation_and_rule_edit_are_serial_and_idempotent(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Main", "0")
        category = _category(client, headers, "Salary", "income")
        today = _horizon_today(client, headers)

        duplicate_rule = client.post(
            "/api/v1/scheduling/rules",
            headers=headers,
            json=_rule_payload(
                operation_type="income",
                start_on=today,
                end_on=today,
                amount="10",
                account_id=account,
                category_id=category,
            ),
        ).json()
        duplicate_occurrence = _occurrences(client, duplicate_rule["id"])[0]

    confirm_barrier = Barrier(2)

    def confirm_same_occurrence() -> tuple[int, str | None]:
        with TestClient(app) as concurrent_client:
            assert (
                concurrent_client.post(
                    "/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}
                ).status_code
                == 200
            )
            confirm_barrier.wait()
            response = concurrent_client.post(
                f"/api/v1/scheduling/occurrences/{duplicate_occurrence['id']}/confirm",
                headers=_headers(concurrent_client),
                json={"version": duplicate_occurrence["version"]},
            )
            return response.status_code, response.json().get("actual_operation_id")

    with ThreadPoolExecutor(max_workers=2) as executor:
        confirmations = list(executor.map(lambda _: confirm_same_occurrence(), range(2)))
    assert [status_code for status_code, _ in confirmations] == [200, 200]
    assert len({operation_id for _, operation_id in confirmations}) == 1

    with TestClient(app) as client:
        assert (
            client.post("/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}).status_code
            == 200
        )
        headers = _headers(client)
        serial_rule = client.post(
            "/api/v1/scheduling/rules",
            headers=headers,
            json=_rule_payload(
                operation_type="income",
                start_on=today,
                end_on=today,
                amount="10",
                account_id=account,
                category_id=category,
            ),
        ).json()
        serial_occurrence = _occurrences(client, serial_rule["id"])[0]

    race_barrier = Barrier(2)

    def update_rule_concurrently() -> int:
        with TestClient(app) as concurrent_client:
            assert (
                concurrent_client.post(
                    "/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}
                ).status_code
                == 200
            )
            replacement = _rule_payload(
                operation_type="income",
                start_on=today,
                end_on=today,
                amount="20",
                account_id=account,
                category_id=category,
            )
            replacement.update({"active": True, "version": serial_rule["version"]})
            race_barrier.wait()
            return concurrent_client.put(
                f"/api/v1/scheduling/rules/{serial_rule['id']}",
                headers=_headers(concurrent_client),
                json=replacement,
            ).status_code

    def confirm_while_rule_changes() -> int:
        with TestClient(app) as concurrent_client:
            assert (
                concurrent_client.post(
                    "/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}
                ).status_code
                == 200
            )
            race_barrier.wait()
            return concurrent_client.post(
                f"/api/v1/scheduling/occurrences/{serial_occurrence['id']}/confirm",
                headers=_headers(concurrent_client),
                json={"version": serial_occurrence["version"]},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        update_future = executor.submit(update_rule_concurrently)
        confirm_future = executor.submit(confirm_while_rule_changes)
        assert update_future.result() == 200
        confirmation_status = confirm_future.result()
        assert confirmation_status in {200, 409}

    with app.state.session_factory() as session:
        persisted = session.get(ExpectedOccurrence, serial_occurrence["id"])
        assert persisted is not None
        if confirmation_status == 200:
            assert persisted.status == "confirmed"
            assert persisted.actual_operation_id is not None
            movement = session.scalar(
                select(AccountMovement).where(
                    AccountMovement.operation_id == persisted.actual_operation_id
                )
            )
            assert movement is not None
            assert movement.amount == persisted.amount
        else:
            assert persisted.status == "pending"
            assert persisted.actual_operation_id is None
            assert persisted.amount == 20


def test_confirmation_failure_rolls_back_actual_operation_and_link(
    postgres_database_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Main", "0")
        category = _category(client, headers, "Salary", "income")
        today = _horizon_today(client, headers)
        rule = client.post(
            "/api/v1/scheduling/rules",
            headers=headers,
            json=_rule_payload(
                operation_type="income",
                start_on=today,
                end_on=today,
                amount="10",
                account_id=account,
                category_id=category,
            ),
        ).json()
        occurrence = _occurrences(client, rule["id"])[0]

        with app.state.session_factory() as session:
            operations_before = session.scalar(select(func.count()).select_from(FinancialOperation))
            movements_before = session.scalar(select(func.count()).select_from(AccountMovement))

        def fail_after_posting(expected: ExpectedOccurrence, operation_id: object) -> None:
            assert expected.id is not None
            assert operation_id is not None
            raise RuntimeError("injected failure after scheduled posting")

        monkeypatch.setattr(scheduling_service, "_link_confirmed_operation", fail_after_posting)
        with pytest.raises(RuntimeError, match="after scheduled posting"):
            client.post(
                f"/api/v1/scheduling/occurrences/{occurrence['id']}/confirm",
                headers=headers,
                json={"version": occurrence["version"]},
            )

        with app.state.session_factory() as session:
            assert (
                session.scalar(select(func.count()).select_from(FinancialOperation))
                == operations_before
            )
            assert (
                session.scalar(select(func.count()).select_from(AccountMovement))
                == movements_before
            )
            persisted = session.get(ExpectedOccurrence, occurrence["id"])
            assert persisted is not None
            assert persisted.status == "pending"
            assert persisted.actual_operation_id is None


def test_alpha4_database_upgrades_and_beta1_schema_downgrades(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Preserved", "10")
        category = _category(client, headers, "Income", "income")

    config = Config("alembic.ini")
    command.downgrade(config, "0005_virtual_funds")
    command.upgrade(config, "head")
    command.check(config)
    upgraded_app = create_app(postgres_database_settings)
    with TestClient(upgraded_app) as client:
        assert (
            client.post("/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}).status_code
            == 200
        )
        headers = _headers(client)
        today = _horizon_today(client, headers)
        created = client.post(
            "/api/v1/scheduling/rules",
            headers=headers,
            json=_rule_payload(
                operation_type="income",
                start_on=today,
                end_on=today,
                amount="1",
                account_id=account,
                category_id=category,
            ),
        )
        assert created.status_code == 201

    command.downgrade(config, "0005_virtual_funds")
    with upgraded_app.state.database_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(FinancialOperation)) == 1
        assert connection.scalar(select(func.count()).select_from(AccountMovement)) == 1


def test_flexible_weekly_rule_round_trips_and_materializes_selected_days(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        headers = _headers(client)
        account = _account(client, headers, "Flexible", "0")
        category = _category(client, headers, "Salary", "income")
        today = _horizon_today(client, headers)
        monday = today + timedelta(days=8 - today.isoweekday())
        payload = _rule_payload(
            operation_type="income",
            start_on=monday,
            end_on=monday + timedelta(days=20),
            amount="10",
            account_id=account,
            category_id=category,
        )
        payload.update({"frequency": "weekly", "interval": 2, "weekdays": [1, 5]})

        created = client.post("/api/v1/scheduling/rules", headers=headers, json=payload)
        assert created.status_code == 201
        assert created.json()["interval"] == 2
        assert created.json()["weekdays"] == [1, 5]
        due_dates = [
            date.fromisoformat(str(item["due_on"]))
            for item in _occurrences(client, created.json()["id"])
        ]
        assert due_dates == [
            monday,
            monday + timedelta(days=4),
            monday + timedelta(days=14),
            monday + timedelta(days=18),
        ]

    rule_id = created.json()["id"]
    with pytest.raises(IntegrityError), app.state.session_factory.begin() as session:
        session.execute(
            update(RecurringRule).where(RecurringRule.id == rule_id).values(weekdays=[1, 1])
        )
    with pytest.raises(IntegrityError), app.state.session_factory.begin() as session:
        session.execute(
            update(RecurringRule)
            .where(RecurringRule.id == rule_id)
            .values(
                frequency=RecurrenceFrequency.DAILY,
                interval=2,
                weekdays=None,
            )
        )
