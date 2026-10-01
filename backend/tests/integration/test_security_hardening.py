from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import app.application.setup as setup_coordinator
import app.modules.auth.service as auth_service
from app.core.config import Settings
from app.main import create_app
from app.modules.auth.contracts import is_initialized, setup_owner
from app.modules.auth.models import ClientLoginThrottle, LoginThrottle, OwnerCredential
from app.modules.auth.security import verify_password
from app.modules.auth.service import PASSWORD_WORK_LOCK

PASSWORD = "correct-master-password"
SETUP = {"master_password": PASSWORD, "base_currency": "RUB", "timezone": "UTC"}


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": str(client.cookies.get("XSRF-TOKEN"))}


def test_initialized_setup_rejects_before_any_backup_processing(
    postgres_database_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as owner:
        assert owner.post("/api/v1/setup", json=SETUP).status_code == 201
        plain = owner.get("/api/v1/backup/export").json()
        encrypted = owner.post(
            "/api/v1/backup/export/hermes", json={"master_password": PASSWORD}, headers=csrf(owner)
        ).json()

        def forbidden_open(*args: object, **kwargs: object) -> None:
            pytest.fail("Initialized setup must not parse or derive a backup key")

        monkeypatch.setattr(setup_coordinator, "open_backup", forbidden_open)
        with TestClient(app) as anonymous:
            for backup in [plain, encrypted, {}, {"format": "hermes"}]:
                response = anonymous.post(
                    "/api/v1/setup/restore",
                    json={
                        "master_password": PASSWORD,
                        "backup": backup,
                        "backup_password": "wrong-backup-password",
                    },
                )
                assert response.status_code == 409
                assert response.json()["detail"]["code"] == "already_initialized"


def test_first_setup_rejects_concurrent_crypto_work_without_partial_state(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        with app.state.session_factory.begin() as locking:
            locking.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": PASSWORD_WORK_LOCK})
            response = client.post(
                "/api/v1/setup/restore", json={"master_password": PASSWORD, "backup": {}}
            )
            assert response.status_code == 429
            assert response.headers["retry-after"] == "1"
            assert client.post("/api/v1/setup", json=SETUP).status_code == 429
            assert client.get("/api/v1/setup/status").json() == {"initialized": False}
        assert client.post("/api/v1/setup", json=SETUP).status_code == 201


def test_anonymous_source_block_survives_restart_but_not_other_owner_actions(
    postgres_database_settings: Settings,
) -> None:
    settings = postgres_database_settings.model_copy(update={"login_failure_limit": 2})
    app = create_app(settings)
    with TestClient(app, client=("192.0.2.1", 1234)) as owner:
        assert owner.post("/api/v1/setup", json=SETUP).status_code == 201
        with TestClient(app, client=("192.0.2.2", 1234)) as attacker:
            assert (
                attacker.post("/api/v1/auth/login", json={"master_password": "wrong"}).status_code
                == 401
            )
            assert (
                attacker.post("/api/v1/auth/login", json={"master_password": "wrong"}).status_code
                == 429
            )
            assert (
                attacker.post(
                    "/api/v1/auth/login",
                    json={"master_password": PASSWORD},
                    headers={"X-Forwarded-For": "192.0.2.3"},
                ).status_code
                == 429
            )
        with TestClient(create_app(settings), client=("192.0.2.2", 1234)) as restarted:
            assert (
                restarted.post("/api/v1/auth/login", json={"master_password": PASSWORD}).status_code
                == 429
            )
        assert (
            owner.post("/api/v1/auth/login", json={"master_password": PASSWORD}).status_code == 200
        )
        assert (
            owner.post(
                "/api/v1/backup/export/hermes",
                headers=csrf(owner),
                json={"master_password": PASSWORD},
            ).status_code
            == 200
        )
        assert (
            owner.post(
                "/api/v1/auth/password",
                headers=csrf(owner),
                json={"current_password": PASSWORD, "new_master_password": "new-master-password"},
            ).status_code
            == 204
        )
        with app.state.session_factory() as session:
            assert session.get(LoginThrottle, 1).failed_count == 0
            assert (
                session.scalar(
                    select(ClientLoginThrottle).where(ClientLoginThrottle.failed_count == 2)
                )
                is not None
            )


def test_password_change_failure_commits_and_shares_sensitive_action_block(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings.model_copy(update={"login_failure_limit": 2}))
    with TestClient(app) as owner, TestClient(app, client=("192.0.2.2", 1234)) as other:
        assert owner.post("/api/v1/setup", json=SETUP).status_code == 201
        assert (
            other.post("/api/v1/auth/login", json={"master_password": PASSWORD}).status_code == 200
        )
        payload = {"current_password": "wrong", "new_master_password": "new-master-password"}
        assert (
            owner.post("/api/v1/auth/password", headers=csrf(owner), json=payload).status_code
            == 400
        )
        with app.state.session_factory() as session:
            throttle = session.get(LoginThrottle, 1)
            assert throttle is not None and throttle.failed_count == 1
        assert (
            owner.post("/api/v1/auth/password", headers=csrf(owner), json=payload).status_code
            == 429
        )
        payload["current_password"] = PASSWORD
        assert (
            owner.post("/api/v1/auth/password", headers=csrf(owner), json=payload).status_code
            == 429
        )
        assert (
            owner.post(
                "/api/v1/backup/export/hermes",
                headers=csrf(owner),
                json={"master_password": PASSWORD},
            ).status_code
            == 429
        )
        assert other.get("/api/v1/auth/session").status_code == 200
        with app.state.session_factory.begin() as session:
            credential = session.get(OwnerCredential, 1)
            assert credential is not None and verify_password(credential.password_hash, PASSWORD)
            throttle = session.get(LoginThrottle, 1)
            assert throttle is not None
            throttle.blocked_until = datetime.now(UTC) - timedelta(seconds=1)
            throttle.window_started_at = datetime.now(UTC) - timedelta(hours=1)
        assert (
            owner.post("/api/v1/auth/password", headers=csrf(owner), json=payload).status_code
            == 204
        )
        assert owner.get("/api/v1/auth/session").status_code == 200
        assert other.get("/api/v1/auth/session").status_code == 401


def test_distributed_attempts_cannot_bypass_global_work_admission(
    postgres_database_settings: Settings,
) -> None:
    settings = postgres_database_settings.model_copy(update={"login_admission_interval_ms": 5000})
    app = create_app(settings)
    with TestClient(app, client=("192.0.2.1", 1234)) as first:
        assert first.post("/api/v1/setup", json=SETUP).status_code == 201
        assert (
            first.post("/api/v1/auth/login", json={"master_password": "wrong"}).status_code == 401
        )
        with TestClient(app, client=("192.0.2.2", 1234)) as second:
            response = second.post("/api/v1/auth/login", json={"master_password": PASSWORD})
            assert response.status_code == 429
            assert response.json()["detail"]["code"] == "auth_work_busy"
        with app.state.session_factory.begin() as session:
            throttle = session.get(LoginThrottle, 1)
            assert throttle is not None
            throttle.next_login_at = datetime.now(UTC) - timedelta(seconds=1)
        with TestClient(app, client=("192.0.2.2", 1234)) as second:
            assert (
                second.post("/api/v1/auth/login", json={"master_password": PASSWORD}).status_code
                == 200
            )


def test_blocked_source_does_not_consume_global_admission(
    postgres_database_settings: Settings,
) -> None:
    settings = postgres_database_settings.model_copy(
        update={"login_failure_limit": 1, "login_admission_interval_ms": 5000}
    )
    app = create_app(settings)
    with TestClient(app, client=("192.0.2.1", 1234)) as attacker:
        assert attacker.post("/api/v1/setup", json=SETUP).status_code == 201
        assert (
            attacker.post("/api/v1/auth/login", json={"master_password": "wrong"}).status_code
            == 429
        )
        with app.state.session_factory.begin() as session:
            row = session.get(LoginThrottle, 1)
            assert row is not None
            row.next_login_at = datetime.now(UTC) - timedelta(seconds=1)
            available_at = row.next_login_at
        assert (
            attacker.post("/api/v1/auth/login", json={"master_password": "wrong"}).json()["detail"][
                "code"
            ]
            == "login_rate_limited"
        )
        with app.state.session_factory() as session:
            row = session.get(LoginThrottle, 1)
            assert row is not None and row.next_login_at == available_at
        with TestClient(app, client=("192.0.2.2", 1234)) as owner:
            assert (
                owner.post("/api/v1/auth/login", json={"master_password": PASSWORD}).status_code
                == 200
            )


def test_source_table_is_bounded_and_expired_rows_are_reclaimed(
    postgres_database_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_service, "MAX_CLIENT_THROTTLES", 2)
    app = create_app(postgres_database_settings)
    with TestClient(app) as setup:
        assert setup.post("/api/v1/setup", json=SETUP).status_code == 201
        for peer in ["192.0.2.1", "192.0.2.2"]:
            with TestClient(app, client=(peer, 1234)) as caller:
                assert (
                    caller.post("/api/v1/auth/login", json={"master_password": "wrong"}).status_code
                    == 401
                )
        with TestClient(app, client=("192.0.2.3", 1234)) as third:
            assert (
                third.post("/api/v1/auth/login", json={"master_password": "wrong"}).status_code
                == 401
            )
            assert (
                third.post("/api/v1/auth/login", json={"master_password": PASSWORD}).status_code
                == 200
            )
            with app.state.session_factory.begin() as session:
                rows = list(session.scalars(select(ClientLoginThrottle)))
                assert len(rows) == 2
                for row in rows:
                    row.window_started_at = datetime.now(UTC) - timedelta(days=2)
            assert (
                third.post("/api/v1/auth/login", json={"master_password": PASSWORD}).status_code
                == 200
            )
            with app.state.session_factory() as session:
                assert len(list(session.scalars(select(ClientLoginThrottle)))) == 1


def test_setup_committing_between_early_check_and_admission_never_opens_backup(
    postgres_database_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(postgres_database_settings)
    original_check = is_initialized
    raced = False
    with TestClient(app) as client:

        def competing_commit(session: Session) -> bool:
            nonlocal raced
            initialized = original_check(session)
            if not initialized and not raced:
                raced = True
                with app.state.session_factory.begin() as competing:
                    setup_owner(
                        competing,
                        postgres_database_settings,
                        master_password=PASSWORD,
                        base_currency="RUB",
                        timezone="UTC",
                    )
            return initialized

        def forbidden_open(*args: object, **kwargs: object) -> None:
            pytest.fail("The instance closed while awaiting admission; no backup work is allowed")

        monkeypatch.setattr(setup_coordinator, "is_initialized", competing_commit)
        monkeypatch.setattr(setup_coordinator, "open_backup", forbidden_open)
        assert (
            client.post(
                "/api/v1/setup/restore", json={"master_password": PASSWORD, "backup": {}}
            ).status_code
            == 409
        )
        assert raced
        assert client.get("/api/v1/setup/status").json() == {"initialized": True}
