from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app import APP_VERSION
from app.core.config import Settings
from app.core.http_limits import MAX_BACKUP_BYTES
from app.main import create_app
from app.modules.auth.models import AuthSession, OwnerCredential
from app.modules.backup.schemas import BackupDocument
from app.modules.backup.service import BackupInvariantError, seal_backup, verify_integrity
from app.modules.settings.models import ApplicationSettings

MASTER_PASSWORD = "correct-master-password"
SETUP = {
    "master_password": MASTER_PASSWORD,
    "base_currency": "RUB",
    "timezone": "Europe/Moscow",
}


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": str(client.cookies.get("XSRF-TOKEN"))}


def reset_to_uninitialized(app: FastAPI) -> None:
    with app.state.session_factory.begin() as session:
        session.execute(delete(AuthSession))
        session.execute(delete(OwnerCredential))
        session.execute(delete(ApplicationSettings))


def test_first_run_restore_is_atomic_and_uses_backup_settings(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP).status_code == 201
        headers = csrf(client)
        parent = client.post(
            "/api/v1/categories",
            headers=headers,
            json={"type": "expense", "name": "Parent"},
        ).json()
        child = client.post(
            "/api/v1/categories",
            headers=headers,
            json={"type": "expense", "name": "Child", "parent_id": parent["id"]},
        ).json()
        backup = client.get("/api/v1/backup/export").json()
        backup["data"]["categories"].sort(key=lambda item: item["parent_id"] is None)
        backup = seal_backup(BackupDocument.model_validate(backup)).model_dump(mode="json")
        assert backup["data"]["categories"][0]["id"] == child["id"]
        reset_to_uninitialized(app)

        restored = client.post(
            "/api/v1/setup/restore",
            json={"master_password": "new-correct-master-password", "backup": backup},
        )
        assert restored.status_code == 201
        assert restored.json()["authenticated"] is True
        assert client.get("/api/v1/settings").json()["timezone"] == "Europe/Moscow"
        restored_categories = {item["id"]: item for item in client.get("/api/v1/categories").json()}
        assert restored_categories[child["id"]]["parent_id"] == parent["id"]
        repeated = client.post(
            "/api/v1/setup/restore",
            json={"master_password": "x" * 12, "backup": backup},
        )
        assert repeated.status_code == 409


def test_invalid_first_run_restore_leaves_instance_uninitialized(
    postgres_database_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP).status_code == 201
        backup = client.get("/api/v1/backup/export").json()
        reset_to_uninitialized(app)
        invalid_backup = deepcopy(backup)
        invalid_backup["integrity"]["digest"] = "0" * 64

        oversized = client.post(
            "/api/v1/setup/restore",
            headers={"Content-Length": str(MAX_BACKUP_BYTES + 1)},
            content=b"{}",
        )
        assert oversized.status_code == 413

        rejected = client.post(
            "/api/v1/setup/restore",
            json={"master_password": "new-correct-master-password", "backup": invalid_backup},
        )
        assert rejected.status_code == 422
        assert client.get("/api/v1/setup/status").json() == {"initialized": False}

        def fail_after_owner_setup(*args: object, **kwargs: object) -> None:
            raise BackupInvariantError("forced restore failure")

        monkeypatch.setattr("app.application.setup.restore_backup", fail_after_owner_setup)
        rolled_back = client.post(
            "/api/v1/setup/restore",
            json={"master_password": "new-correct-master-password", "backup": backup},
        )
        assert rolled_back.status_code == 422
        assert client.get("/api/v1/setup/status").json() == {"initialized": False}
        assert client.get("/api/v1/auth/session").status_code == 401


def test_export_preview_and_transactional_restore_on_initialized_database(
    postgres_database_settings: Settings,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        assert client.get("/api/v1/backup/export").status_code == 401
        assert client.post("/api/v1/setup", json=SETUP).status_code == 201
        headers = csrf(client)
        account = client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"type": "debit", "name": "Main", "initial_balance": "125.5000"},
        ).json()
        category = client.post(
            "/api/v1/categories",
            headers=headers,
            json={"type": "expense", "name": "Food"},
        ).json()

        exported = client.get("/api/v1/backup/export")
        assert exported.status_code == 200
        assert exported.headers["cache-control"] == "no-store"
        document = exported.json()
        assert document["format"] == "hermes-json-backup"
        assert document["schema_version"] == 1
        assert document["app_version"] == "1.1.0"
        assert document["data"]["account_movements"][0]["amount"] == "125.5000"
        assert "password" not in exported.text
        assert "sessions" not in document["data"]
        verify_integrity(BackupDocument.model_validate(document))

        preview = client.post("/api/v1/backup/preview", headers=headers, json=document)
        assert preview.status_code == 200
        assert preview.json()["integrity_verified"] is True
        assert preview.json()["counts"]["accounts"] == 1
        assert client.post("/api/v1/backup/preview", json=document).status_code == 403
        oversized = client.post(
            "/api/v1/backup/preview",
            headers={**headers, "Content-Length": str(MAX_BACKUP_BYTES + 1)},
            content=b"{}",
        )
        assert oversized.status_code == 413
        assert oversized.json()["detail"]["code"] == "backup_too_large"

        tampered = deepcopy(document)
        tampered["data"]["accounts"][0]["name"] = "Tampered"
        rejected = client.post("/api/v1/backup/preview", headers=headers, json=tampered)
        assert rejected.status_code == 422
        assert rejected.json()["detail"]["code"] == "invalid_backup"

        assert (
            client.delete(f"/api/v1/accounts/{account['id']}", headers=headers).status_code == 409
        )
        wrong_password = client.post(
            "/api/v1/backup/restore",
            headers=headers,
            json={
                "backup": document,
                "confirmation": "ЗАМЕНИТЬ ВСЕ ДАННЫЕ",
                "master_password": "wrong-master-password",
            },
        )
        assert wrong_password.status_code == 400
        wrong_confirmation = client.post(
            "/api/v1/backup/restore",
            headers=headers,
            json={
                "backup": document,
                "confirmation": "заменить",
                "master_password": MASTER_PASSWORD,
            },
        )
        assert wrong_confirmation.status_code == 400
        assert wrong_confirmation.json()["detail"]["code"] == "confirmation_invalid"

        restored = client.post(
            "/api/v1/backup/restore",
            headers=headers,
            json={
                "backup": document,
                "confirmation": "ЗАМЕНИТЬ ВСЕ ДАННЫЕ",
                "master_password": MASTER_PASSWORD,
            },
        )
        assert restored.status_code == 200
        assert restored.json()["counts"]["categories"] == 1
        assert client.get(f"/api/v1/accounts/{account['id']}").json()["balance"] == "125.5000"
        assert client.get("/api/v1/categories").json()[0]["id"] == category["id"]


def test_protected_hermes_export_and_first_run_restore_use_separate_passwords(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP).status_code == 201
        headers = csrf(client)
        account = client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"type": "debit", "name": "Sensitive account", "initial_balance": "125.5000"},
        ).json()

        wrong_export_password = client.post(
            "/api/v1/backup/export/hermes",
            headers=headers,
            json={"master_password": "wrong-master-password"},
        )
        assert wrong_export_password.status_code == 400
        assert wrong_export_password.json()["detail"]["code"] == "current_password_invalid"

        exported = client.post(
            "/api/v1/backup/export/hermes",
            headers=headers,
            json={"master_password": MASTER_PASSWORD},
        )
        assert exported.status_code == 200
        assert exported.headers["cache-control"] == "no-store"
        assert exported.headers["content-disposition"].endswith('"hermes-backup.hermes"')
        hermes = exported.json()
        assert hermes["format"] == "hermes"
        assert hermes["version"] == 1
        assert hermes["kdf"]["algorithm"] == "argon2id"
        assert hermes["key_encryption"]["algorithm"] == "xchacha20-poly1305-ietf"
        assert "Sensitive account" not in exported.text
        assert "125.5000" not in exported.text
        assert "data" not in hermes

        rejected = client.post(
            "/api/v1/backup/preview",
            headers=headers,
            json={"backup": hermes, "backup_password": "wrong-backup-password"},
        )
        assert rejected.status_code == 400
        assert rejected.json()["detail"]["code"] == "backup_authentication_failed"
        preview = client.post(
            "/api/v1/backup/preview",
            headers=headers,
            json={"backup": hermes, "backup_password": MASTER_PASSWORD},
        )
        assert preview.status_code == 200
        assert preview.json()["format"] == "hermes"
        assert preview.json()["counts"]["accounts"] == 1

        extra_account = client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"type": "cash", "name": "Not in backup", "initial_balance": "10"},
        ).json()
        wrong_backup_password = client.post(
            "/api/v1/backup/restore",
            headers=headers,
            json={
                "backup": hermes,
                "confirmation": "ЗАМЕНИТЬ ВСЕ ДАННЫЕ",
                "master_password": MASTER_PASSWORD,
                "backup_password": "wrong-backup-password",
            },
        )
        assert wrong_backup_password.status_code == 400
        assert wrong_backup_password.json()["detail"]["code"] == "backup_authentication_failed"
        assert client.get(f"/api/v1/accounts/{extra_account['id']}").status_code == 200

        wrong_destination_password = client.post(
            "/api/v1/backup/restore",
            headers=headers,
            json={
                "backup": hermes,
                "confirmation": "ЗАМЕНИТЬ ВСЕ ДАННЫЕ",
                "master_password": "wrong-current-password",
                "backup_password": MASTER_PASSWORD,
            },
        )
        assert wrong_destination_password.status_code == 400
        assert wrong_destination_password.json()["detail"]["code"] == "current_password_invalid"

        initialized_restore = client.post(
            "/api/v1/backup/restore",
            headers=headers,
            json={
                "backup": hermes,
                "confirmation": "ЗАМЕНИТЬ ВСЕ ДАННЫЕ",
                "master_password": MASTER_PASSWORD,
                "backup_password": MASTER_PASSWORD,
            },
        )
        assert initialized_restore.status_code == 200
        assert client.get(f"/api/v1/accounts/{extra_account['id']}").status_code == 404
        assert client.get(f"/api/v1/accounts/{account['id']}").status_code == 200

        reset_to_uninitialized(app)
        restored = client.post(
            "/api/v1/setup/restore",
            json={
                "master_password": "new-destination-password",
                "backup_password": MASTER_PASSWORD,
                "backup": hermes,
            },
        )
        assert restored.status_code == 201
        restored_account = client.get(f"/api/v1/accounts/{account['id']}")
        assert restored_account.status_code == 200
        assert restored_account.json()["balance"] == "125.5000"


def test_restore_complete_backup_into_clean_initialized_target(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP).status_code == 201
        headers = csrf(client)
        account = client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"type": "debit", "name": "Main", "initial_balance": "100"},
        ).json()
        category = client.post(
            "/api/v1/categories",
            headers=headers,
            json={"type": "expense", "name": "Food"},
        ).json()
        fund = client.post(
            "/api/v1/funds",
            headers=headers,
            json={"name": "Reserve", "description": None, "allocation_percentage": "10"},
        ).json()
        destination_fund = client.post(
            "/api/v1/funds",
            headers=headers,
            json={"name": "Goal", "description": None, "allocation_percentage": "0"},
        ).json()
        assert (
            client.post(
                "/api/v1/funds/allocations",
                headers=headers,
                json={
                    "account_id": account["id"],
                    "amount": "20",
                    "occurred_on": "2026-08-12",
                    "description": "Reserve",
                    "allocations": [{"fund_id": fund["id"], "amount": "10"}],
                },
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/v1/funds/transfers",
                headers=headers,
                json={
                    "source_fund_id": fund["id"],
                    "destination_fund_id": destination_fund["id"],
                    "account_id": account["id"],
                    "amount": "4",
                    "occurred_on": "2026-08-12",
                    "description": "Move between goals",
                },
            ).status_code
            == 201
        )
        rule = client.post(
            "/api/v1/scheduling/rules",
            headers=headers,
            json={
                "type": "expense",
                "frequency": "monthly",
                "start_on": "2026-08-12",
                "amount": "5",
                "description": "Food",
                "account_id": account["id"],
                "category_id": category["id"],
                "shift_future_on_postpone": True,
            },
        )
        assert rule.status_code == 201
        rule_data = rule.json()
        occurrence = next(
            item
            for item in client.get("/api/v1/scheduling/occurrences?page_size=367").json()["items"]
            if item["rule_id"] == rule_data["id"]
        )
        shifted_due_on = date.fromisoformat(occurrence["due_on"]) + timedelta(days=4)
        postponed = client.post(
            f"/api/v1/scheduling/occurrences/{occurrence['id']}/postpone",
            headers=headers,
            json={
                "version": occurrence["version"],
                "rule_version": rule_data["version"],
                "due_on": shifted_due_on.isoformat(),
            },
        )
        assert postponed.status_code == 200
        document = client.get("/api/v1/backup/export").json()
        preserved_record = next(
            item
            for item in document["data"]["expected_occurrences"]
            if item["id"] != occurrence["id"]
        )
        preserved_record["status"] = "cancelled"
        preserved_record["preserve_from_series_shift"] = True
        preserved_id = preserved_record["id"]
        document = seal_backup(BackupDocument.model_validate(document)).model_dump(mode="json")

        factory = app.state.session_factory
        with factory.begin() as session:
            from app.modules.backup.schemas import BackupData, BackupIntegrity, SettingsRecord
            from app.modules.backup.service import FORMAT, SCHEMA_VERSION, restore_backup

            settings = document["data"]["settings"]
            empty = BackupData(
                settings=SettingsRecord.model_validate(settings),
                accounts=[],
                categories=[],
                operations=[],
                account_movements=[],
                funds=[],
                fund_events=[],
                fund_movements=[],
                recurring_rules=[],
                expected_occurrences=[],
            )
            blank = BackupDocument(
                format=FORMAT,
                schema_version=SCHEMA_VERSION,
                app_version=APP_VERSION,
                exported_at=document["exported_at"],
                data=empty,
                integrity=BackupIntegrity(digest="0" * 64),
            )
            restore_backup(session, seal_backup(blank))

        restored = client.post(
            "/api/v1/backup/restore",
            headers=headers,
            json={
                "backup": document,
                "confirmation": "ЗАМЕНИТЬ ВСЕ ДАННЫЕ",
                "master_password": MASTER_PASSWORD,
            },
        )
        assert restored.status_code == 200
        assert restored.json()["counts"]["fund_movements"] == 3
        assert restored.json()["counts"]["recurring_rules"] == 1
        assert client.get("/api/v1/funds/summary").json()["total_reserved"] == "10.0000"
        restored_positions = {
            item["fund_id"]: item["balance"]
            for item in client.get("/api/v1/funds/summary").json()["positions"]
        }
        assert restored_positions == {fund["id"]: "6.0000", destination_fund["id"]: "4.0000"}
        restored_rule = client.get("/api/v1/scheduling/rules").json()[0]
        assert restored_rule["shift_future_on_postpone"] is True
        assert restored_rule["series_shift_days"] == 4
        restored_occurrence = next(
            item
            for item in client.get("/api/v1/scheduling/occurrences?page_size=367").json()["items"]
            if item["rule_id"] == restored_rule["id"]
        )
        assert restored_occurrence["series_shift_days"] == 4
        assert restored_occurrence["due_on"] == shifted_due_on.isoformat()
        restored_preserved = next(
            item
            for item in client.get("/api/v1/scheduling/occurrences?page_size=367").json()["items"]
            if item["id"] == preserved_id
        )
        assert restored_preserved["status"] == "cancelled"
        assert restored_preserved["preserve_from_series_shift"] is True


def test_backup_round_trips_dynamic_fund_allocation_mode(
    postgres_database_settings: Settings,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        assert client.post("/api/v1/setup", json=SETUP).status_code == 201
        headers = csrf(client)
        assert (
            client.post(
                "/api/v1/funds",
                headers=headers,
                json={
                    "name": "Reserve",
                    "target_amount": "100",
                    "allocation_percentage": "25",
                },
            ).status_code
            == 201
        )
        switched = client.put(
            "/api/v1/settings/fund-allocation-mode",
            headers=headers,
            json={"mode": "dynamic"},
        )
        assert switched.status_code == 200
        assert (
            client.post(
                "/api/v1/funds",
                headers=headers,
                json={
                    "name": "Second",
                    "target_amount": "100",
                    "allocation_percentage": "100",
                },
            ).status_code
            == 201
        )
        document = client.get("/api/v1/backup/export").json()
        assert document["data"]["settings"]["fund_allocation_mode"] == "dynamic"
        assert sum(
            Decimal(item["allocation_percentage"]) for item in document["data"]["funds"]
        ) > Decimal("100")

        restored = client.post(
            "/api/v1/backup/restore",
            headers=headers,
            json={
                "backup": document,
                "confirmation": "ЗАМЕНИТЬ ВСЕ ДАННЫЕ",
                "master_password": MASTER_PASSWORD,
            },
        )
        assert restored.status_code == 200
        assert client.get("/api/v1/settings").json()["fund_allocation_mode"] == "dynamic"
        assert {item["allocation_percentage"] for item in client.get("/api/v1/funds").json()} == {
            "50.0000"
        }


def test_failed_restore_rolls_back_existing_data(postgres_database_settings: Settings) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        assert client.post("/api/v1/setup", json=SETUP).status_code == 201
        headers = csrf(client)
        account = client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"type": "cash", "name": "Safe", "initial_balance": "10"},
        ).json()
        document = client.get("/api/v1/backup/export").json()
        document["data"]["account_movements"][0]["amount"] = "-10.0000"
        document = seal_backup(BackupDocument.model_validate(document)).model_dump(mode="json")
        rejected = client.post(
            "/api/v1/backup/restore",
            headers=headers,
            json={
                "backup": document,
                "confirmation": "ЗАМЕНИТЬ ВСЕ ДАННЫЕ",
                "master_password": MASTER_PASSWORD,
            },
        )
        assert rejected.status_code == 422
        assert client.get(f"/api/v1/accounts/{account['id']}").json()["balance"] == "10.0000"


def test_restore_reauthentication_is_rate_limited_and_revokes_other_sessions(
    postgres_database_settings: Settings,
) -> None:
    limited = postgres_database_settings.model_copy(update={"login_failure_limit": 2})
    app = create_app(limited)
    with TestClient(app) as first, TestClient(app) as second:
        assert first.post("/api/v1/setup", json=SETUP).status_code == 201
        assert (
            second.post("/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}).status_code
            == 200
        )
        headers = csrf(first)
        document = first.get("/api/v1/backup/export").json()
        payload = {
            "backup": document,
            "confirmation": "ЗАМЕНИТЬ ВСЕ ДАННЫЕ",
            "master_password": "wrong-master-password",
        }
        assert (
            first.post("/api/v1/backup/restore", headers=headers, json=payload).status_code == 400
        )
        limited_response = first.post("/api/v1/backup/restore", headers=headers, json=payload)
        assert limited_response.status_code == 429
        payload["master_password"] = MASTER_PASSWORD
        assert (
            first.post("/api/v1/backup/restore", headers=headers, json=payload).status_code == 429
        )

        factory = app.state.session_factory
        with factory.begin() as session:
            from app.modules.auth.models import LoginThrottle

            throttle = session.get(LoginThrottle, 1)
            assert throttle is not None
            throttle.failed_count = 0
            throttle.window_started_at = None
            throttle.blocked_until = None

        assert (
            first.post("/api/v1/backup/restore", headers=headers, json=payload).status_code == 200
        )
        assert second.get("/api/v1/auth/session").status_code == 401
