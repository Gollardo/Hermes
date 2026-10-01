from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.application.accounts import set_account_archived_with_default_cleanup
from app.application.settings import replace_application_settings
from app.core.config import Settings
from app.core.database import create_database_engine, create_session_factory
from app.main import create_app
from app.modules.accounts.contracts import AccountReferenceError
from app.modules.auth.models import AuthSession, OwnerCredential
from app.modules.auth.security import hash_password, hash_token
from app.modules.auth.service import LoginStatus, login
from app.modules.categories.models import Category, CategoryType
from app.modules.settings.models import ApplicationSettings
from app.modules.settings.service import (
    BaseCurrencyLockedError,
    lock_base_currency,
    update_application_settings,
)

MASTER_PASSWORD = "correct-master-password"
NEW_MASTER_PASSWORD = "new-correct-master-password"
SETUP_PAYLOAD = {
    "master_password": MASTER_PASSWORD,
    "base_currency": "RUB",
    "timezone": "Europe/Moscow",
}


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("XSRF-TOKEN")
    assert token is not None
    return {"X-XSRF-TOKEN": token}


def test_first_run_protection_login_and_logout(postgres_database_settings: Settings) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/setup/status").json() == {"initialized": False}
        assert client.get("/api/v1/settings").status_code == 401

        invalid = client.post(
            "/api/v1/setup", json={**SETUP_PAYLOAD, "master_password": "too-short"}
        )
        assert invalid.status_code == 422

        setup = client.post("/api/v1/setup", json=SETUP_PAYLOAD)
        assert setup.status_code == 201
        assert setup.json()["authenticated"] is True
        assert setup.json()["idle_timeout_seconds"] == 1800
        assert "HttpOnly" in setup.headers.get_list("set-cookie")[0]
        assert client.get("/api/v1/setup/status").json() == {"initialized": True}
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 409

        settings = client.get("/api/v1/settings")
        assert settings.status_code == 200
        assert settings.json()["base_currency"] == "RUB"
        raw_token = client.cookies.get(postgres_database_settings.session_cookie_name)
        assert raw_token is not None
        with app.state.session_factory() as session:
            before_activity = session.get(AuthSession, hash_token(raw_token))
            assert before_activity is not None
            before_activity_at = before_activity.last_activity_at
        assert client.post("/api/v1/auth/activity").status_code == 403
        assert client.post("/api/v1/auth/activity", headers=csrf_headers(client)).status_code == 204
        with app.state.session_factory() as session:
            after_activity = session.get(AuthSession, hash_token(raw_token))
            assert after_activity is not None
            assert after_activity.last_activity_at >= before_activity_at
        assert client.post("/api/v1/auth/logout").status_code == 403
        assert client.post("/api/v1/auth/logout", headers=csrf_headers(client)).status_code == 204
        assert client.get("/api/v1/auth/session").status_code == 401

        assert (
            client.post(
                "/api/v1/auth/login", json={"master_password": "incorrect-password"}
            ).status_code
            == 401
        )
        login = client.post("/api/v1/auth/login", json={"master_password": MASTER_PASSWORD})
        assert login.status_code == 200
        current = client.get("/api/v1/auth/session")
        assert current.status_code == 200
        assert current.json()["idle_timeout_seconds"] == 1800


def test_setup_creates_only_selected_expense_trees_and_default_income_categories(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/setup",
            json={
                **SETUP_PAYLOAD,
                "create_default_categories": True,
                "onboarding_expense_groups": ["housing", "pets"],
            },
        )
        assert response.status_code == 201

    session_factory = create_session_factory(create_database_engine(postgres_database_settings))
    with session_factory() as session:
        categories = list(session.scalars(select(Category)))
        income_names = {item.name for item in categories if item.type == CategoryType.INCOME}
        expense_names = {item.name for item in categories if item.type == CategoryType.EXPENSE}
        assert income_names == {"Зарплата", "Аванс", "Бизнес", "Процент банка", "Прочее"}
        assert {"🏠 Жильё", "Аренда / ипотека", "🐕 Домашние животные", "Корм"} <= expense_names
        assert "🚗 Автомобиль" not in expense_names
        assert len(categories) == 17
        housing = next(item for item in categories if item.name == "🏠 Жильё")
        rent = next(item for item in categories if item.name == "Аренда / ипотека")
        assert housing.parent_id is None
        assert rent.parent_id == housing.id
        assert all(
            item.parent_id is None for item in categories if item.type == CategoryType.INCOME
        )


def test_skipped_expense_questions_still_create_default_income_categories(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/setup",
            json={**SETUP_PAYLOAD, "create_default_categories": True},
        )
        assert response.status_code == 201

    session_factory = create_session_factory(create_database_engine(postgres_database_settings))
    with session_factory() as session:
        categories = list(session.scalars(select(Category)))
        assert {item.name for item in categories} == {
            "Зарплата",
            "Аванс",
            "Бизнес",
            "Процент банка",
            "Прочее",
        }
        assert all(item.type == CategoryType.INCOME for item in categories)


def test_setup_rejects_duplicate_or_inconsistent_onboarding_groups_without_initializing(
    postgres_database_settings: Settings,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        duplicate = client.post(
            "/api/v1/setup",
            json={
                **SETUP_PAYLOAD,
                "create_default_categories": True,
                "onboarding_expense_groups": ["housing", "housing"],
            },
        )
        assert duplicate.status_code == 422
        inconsistent = client.post(
            "/api/v1/setup",
            json={**SETUP_PAYLOAD, "onboarding_expense_groups": ["housing"]},
        )
        assert inconsistent.status_code == 422
        assert client.get("/api/v1/setup/status").json() == {"initialized": False}


def test_password_change_and_logout_all_revoke_sessions(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as first, TestClient(app) as second:
        assert first.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        assert (
            second.post("/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}).status_code
            == 200
        )

        wrong = first.post(
            "/api/v1/auth/password",
            headers=csrf_headers(first),
            json={
                "current_password": "wrong-current-password",
                "new_master_password": NEW_MASTER_PASSWORD,
            },
        )
        assert wrong.status_code == 400
        changed = first.post(
            "/api/v1/auth/password",
            headers=csrf_headers(first),
            json={
                "current_password": MASTER_PASSWORD,
                "new_master_password": NEW_MASTER_PASSWORD,
            },
        )
        assert changed.status_code == 204
        assert second.get("/api/v1/auth/session").status_code == 401
        assert (
            second.post("/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}).status_code
            == 401
        )
        assert (
            second.post(
                "/api/v1/auth/login", json={"master_password": NEW_MASTER_PASSWORD}
            ).status_code
            == 200
        )

        assert first.post("/api/v1/auth/logout-all", headers=csrf_headers(first)).status_code == 204
        assert first.get("/api/v1/auth/session").status_code == 401
        assert second.get("/api/v1/auth/session").status_code == 401


def test_settings_validation_and_currency_lock(postgres_database_settings: Settings) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        updated = client.put(
            "/api/v1/settings",
            headers=csrf_headers(client),
            json={"base_currency": "eur", "timezone": "UTC"},
        )
        assert updated.status_code == 200
        assert updated.json()["base_currency"] == "EUR"
        account = client.post(
            "/api/v1/accounts",
            headers=csrf_headers(client),
            json={"type": "debit", "name": "Main", "initial_balance": "0"},
        )
        assert account.status_code == 201
        default_account = client.put(
            "/api/v1/settings",
            headers=csrf_headers(client),
            json={
                "base_currency": "EUR",
                "timezone": "UTC",
                "default_account_id": account.json()["id"],
            },
        )
        assert default_account.status_code == 200
        assert default_account.json()["default_account_id"] == account.json()["id"]
        assert (
            client.post(
                f"/api/v1/accounts/{account.json()['id']}/archive",
                headers=csrf_headers(client),
            ).status_code
            == 200
        )
        assert client.get("/api/v1/settings").json()["default_account_id"] is None
        assert (
            client.post(
                f"/api/v1/accounts/{account.json()['id']}/restore",
                headers=csrf_headers(client),
            ).status_code
            == 200
        )
        assert (
            client.put(
                "/api/v1/settings",
                headers=csrf_headers(client),
                json={
                    "base_currency": "EUR",
                    "timezone": "UTC",
                    "default_account_id": account.json()["id"],
                },
            ).status_code
            == 200
        )
        assert (
            client.delete(
                f"/api/v1/accounts/{account.json()['id']}", headers=csrf_headers(client)
            ).status_code
            == 204
        )
        assert client.get("/api/v1/settings").json()["default_account_id"] is None
        account_with_history = client.post(
            "/api/v1/accounts",
            headers=csrf_headers(client),
            json={"type": "debit", "name": "History", "initial_balance": "1"},
        ).json()
        assert (
            client.put(
                "/api/v1/settings",
                headers=csrf_headers(client),
                json={
                    "base_currency": "EUR",
                    "timezone": "UTC",
                    "default_account_id": account_with_history["id"],
                },
            ).status_code
            == 200
        )
        assert (
            client.delete(
                f"/api/v1/accounts/{account_with_history['id']}",
                headers=csrf_headers(client),
            ).status_code
            == 409
        )
        assert (
            client.get("/api/v1/settings").json()["default_account_id"]
            == account_with_history["id"]
        )
        invalid_default = client.put(
            "/api/v1/settings",
            headers=csrf_headers(client),
            json={
                "base_currency": "EUR",
                "timezone": "UTC",
                "default_account_id": "00000000-0000-0000-0000-000000000099",
            },
        )
        assert invalid_default.status_code == 409
        assert invalid_default.json()["detail"]["code"] == "invalid_default_account"
        assert (
            client.put(
                "/api/v1/settings",
                headers=csrf_headers(client),
                json={"base_currency": "EUR", "timezone": "Invalid/Timezone"},
            ).status_code
            == 422
        )

        factory = app.state.session_factory
        with factory.begin() as session:
            lock_base_currency(session)

        locked = client.put(
            "/api/v1/settings",
            headers=csrf_headers(client),
            json={"base_currency": "USD", "timezone": "UTC"},
        )
        assert locked.status_code == 409
        assert (
            client.put(
                "/api/v1/settings",
                headers=csrf_headers(client),
                json={"base_currency": "EUR", "timezone": "Europe/Moscow"},
            ).status_code
            == 200
        )


def test_default_account_selection_serializes_with_archival(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        account_id = UUID(
            client.post(
                "/api/v1/accounts",
                headers=csrf_headers(client),
                json={"type": "debit", "name": "Main", "initial_balance": "0"},
            ).json()["id"]
        )
        start = Barrier(2)

        def select_default() -> str:
            start.wait()
            try:
                with app.state.session_factory.begin() as session:
                    replace_application_settings(
                        session,
                        base_currency="RUB",
                        timezone="Europe/Moscow",
                        default_account_id=account_id,
                    )
            except AccountReferenceError:
                return "rejected"
            return "selected"

        def archive() -> None:
            start.wait()
            with app.state.session_factory.begin() as session:
                set_account_archived_with_default_cleanup(session, account_id, archived=True)

        with ThreadPoolExecutor(max_workers=2) as executor:
            selection = executor.submit(select_default)
            archival = executor.submit(archive)
            archival.result(timeout=5)
            assert selection.result(timeout=5) in {"selected", "rejected"}

        assert client.get(f"/api/v1/accounts/{account_id}").json()["archived"] is True
        assert client.get("/api/v1/settings").json()["default_account_id"] is None


def test_failed_logins_are_rate_limited(postgres_database_settings: Settings) -> None:
    limited_settings = postgres_database_settings.model_copy(
        update={"login_failure_limit": 2, "login_block_minutes": 1}
    )
    with TestClient(create_app(limited_settings)) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        assert client.post("/api/v1/auth/logout", headers=csrf_headers(client)).status_code == 204

        first = client.post("/api/v1/auth/login", json={"master_password": "incorrect-password"})
        second = client.post("/api/v1/auth/login", json={"master_password": "incorrect-password"})
        blocked_correct = client.post(
            "/api/v1/auth/login", json={"master_password": MASTER_PASSWORD}
        )

        assert first.status_code == 401
        assert second.status_code == 429
        assert int(second.headers["retry-after"]) > 0
        assert blocked_correct.status_code == 429


def test_concurrent_failed_logins_admit_only_one_password_worker(
    postgres_database_settings: Settings,
) -> None:
    limited_settings = postgres_database_settings.model_copy(
        update={"login_failure_limit": 2, "login_block_minutes": 1}
    )
    with TestClient(create_app(limited_settings)) as setup_client:
        assert setup_client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201

    engine = create_database_engine(limited_settings)
    factory = create_session_factory(engine)
    start = Barrier(2)

    def attempt_login() -> LoginStatus:
        start.wait()
        with factory.begin() as session:
            return login(
                session,
                limited_settings,
                master_password="incorrect-password",
                client_key="same-source",
            ).status

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(lambda _: attempt_login(), range(2)))
    finally:
        engine.dispose()

    assert sorted(status.value for status in statuses) in [
        ["busy", "invalid"],
        ["blocked", "invalid"],
    ]


def test_currency_update_serializes_with_financial_lock(
    postgres_database_settings: Settings,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201

    engine = create_database_engine(postgres_database_settings)
    factory = create_session_factory(engine)
    try:
        with factory.begin() as locking_session:
            lock_base_currency(locking_session)
            with pytest.raises(OperationalError), factory.begin() as concurrent_session:
                concurrent_session.execute(text("SET LOCAL lock_timeout = '100ms'"))
                update_application_settings(
                    concurrent_session,
                    base_currency="USD",
                    timezone="UTC",
                )

        with factory.begin() as session, pytest.raises(BaseCurrencyLockedError):
            update_application_settings(
                session,
                base_currency="USD",
                timezone="UTC",
            )
    finally:
        engine.dispose()


def test_expired_session_is_rejected(postgres_database_settings: Settings) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        setup = client.post("/api/v1/setup", json=SETUP_PAYLOAD)
        assert setup.status_code == 201
        raw_token = client.cookies.get(postgres_database_settings.session_cookie_name)
        assert raw_token is not None

        now = datetime.now(UTC)
        with app.state.session_factory.begin() as session:
            stored = session.get(AuthSession, hash_token(raw_token))
            assert stored is not None
            stored.created_at = now - timedelta(days=2)
            stored.last_activity_at = now - timedelta(days=1, hours=12)
            stored.expires_at = now - timedelta(days=1)

        assert client.get("/api/v1/auth/session").status_code == 401


def test_idle_session_requires_login_and_is_pruned_on_login(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app) as client:
        assert client.post("/api/v1/setup", json=SETUP_PAYLOAD).status_code == 201
        raw_token = client.cookies.get(postgres_database_settings.session_cookie_name)
        assert raw_token is not None

        with app.state.session_factory.begin() as session:
            stored = session.get(AuthSession, hash_token(raw_token))
            assert stored is not None
            now = datetime.now(UTC)
            stored.created_at = now - timedelta(hours=1)
            stored.last_activity_at = now - timedelta(minutes=31)

        assert client.get("/api/v1/auth/session").status_code == 401
        with app.state.session_factory() as session:
            assert session.get(AuthSession, hash_token(raw_token)) is not None
        assert (
            client.post(
                "/api/v1/auth/login", json={"master_password": SETUP_PAYLOAD["master_password"]}
            ).status_code
            == 200
        )
        with app.state.session_factory() as session:
            assert session.get(AuthSession, hash_token(raw_token)) is None


def test_initialized_database_upgrades_from_0001_to_head(
    postgres_database_settings: Settings,
) -> None:
    command.downgrade(Config("alembic.ini"), "0001_first_run_access")

    raw_token = "legacy-session-token"
    created_at = datetime.now(UTC) - timedelta(days=1)
    engine = create_database_engine(postgres_database_settings)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO auth_owner_credentials "
                    "(id, password_hash, created_at, password_changed_at) "
                    "VALUES (1, :password_hash, :created_at, :created_at)"
                ),
                {"password_hash": hash_password(MASTER_PASSWORD), "created_at": created_at},
            )
            connection.execute(
                text(
                    "INSERT INTO application_settings "
                    "(id, base_currency, timezone, base_currency_locked_at, "
                    "created_at, updated_at) "
                    "VALUES (1, 'RUB', 'Europe/Moscow', NULL, :created_at, :created_at)"
                ),
                {"created_at": created_at},
            )
            connection.execute(
                text(
                    "INSERT INTO auth_sessions "
                    "(token_hash, owner_id, csrf_token_hash, created_at, expires_at) "
                    "VALUES (:token_hash, 1, :csrf_hash, :created_at, :expires_at)"
                ),
                {
                    "token_hash": hash_token(raw_token),
                    "csrf_hash": hash_token("legacy-csrf-token"),
                    "created_at": created_at,
                    "expires_at": created_at + timedelta(days=7),
                },
            )
    finally:
        engine.dispose()

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_database_engine(postgres_database_settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            owner = session.get(OwnerCredential, 1)
            settings = session.get(ApplicationSettings, 1)
            stored_tokens = session.scalars(select(AuthSession.token_hash)).all()
            assert owner is not None
            assert owner.password_hash.startswith("$argon2id$")
            assert settings is not None
            assert settings.base_currency == "RUB"
            assert settings.fund_allocation_mode == "manual"
            assert stored_tokens
            assert raw_token not in stored_tokens
            assert hash_token(raw_token) in stored_tokens
            stored = session.get(AuthSession, hash_token(raw_token))
            assert stored is not None
            assert stored.last_activity_at == stored.created_at
    finally:
        engine.dispose()
