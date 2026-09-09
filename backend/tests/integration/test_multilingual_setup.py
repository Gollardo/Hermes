from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.database import create_database_engine, create_session_factory
from app.main import create_app
from app.modules.auth.models import OwnerCredential
from app.modules.categories.models import Category
from app.modules.settings.models import ApplicationSettings

PAYLOAD = {
    "master_password": "test-master-password",
    "base_currency": "RUB",
    "timezone": "UTC",
    "create_default_categories": True,
    "onboarding_expense_groups": ["housing", "pets"],
}


def headers(client: TestClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": client.cookies["XSRF-TOKEN"]}


@pytest.mark.parametrize(
    "language,salary,housing,rent",
    [
        ("ru", "Зарплата", "🏠 Жильё", "Аренда / ипотека"),
        ("en", "Salary", "🏠 Housing", "Rent / mortgage"),
    ],
)
def test_localized_setup_round_trips_names_without_changing_financial_settings(
    postgres_database_settings: Settings,
    language: str,
    salary: str,
    housing: str,
    rent: str,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        assert (
            client.post(
                "/api/v1/setup", json={**PAYLOAD, "category_template_language": language}
            ).status_code
            == 201
        )
        exported = client.get("/api/v1/backup/export").json()
        categories = exported["data"]["categories"]
        assert len(categories) == 17
        by_name = {item["name"]: item for item in categories}
        assert salary in by_name
        assert by_name[rent]["parent_id"] == by_name[housing]["id"]
        settings = client.get("/api/v1/settings").json()
        assert settings["base_currency"] == "RUB"
        assert settings["timezone"] == "UTC"
        assert settings["base_currency_locked"] is False
        assert "language" not in exported["data"]["settings"]
        assert "category_template_language" not in exported["data"]["settings"]
        # Request locale never renames existing/restored user data.
        other_language = "en" if language == "ru" else "ru"
        client.headers["Accept-Language"] = other_language
        response = client.post(
            "/api/v1/backup/restore",
            headers=headers(client),
            json={
                "backup": exported,
                "confirmation": "ЗАМЕНИТЬ ВСЕ ДАННЫЕ",
                "master_password": PAYLOAD["master_password"],
            },
        )
        assert response.status_code == 200
        restored = client.get("/api/v1/backup/export").json()
        assert restored["data"]["categories"] == categories
        # The public setup boundary still rejects reinitialization.
        assert (
            client.post(
                "/api/v1/setup", json={**PAYLOAD, "category_template_language": other_language}
            ).status_code
            == 409
        )


def test_invalid_language_is_safe_and_does_not_initialize(
    postgres_database_settings: Settings,
) -> None:
    with TestClient(create_app(postgres_database_settings)) as client:
        response = client.post(
            "/api/v1/setup", json={**PAYLOAD, "category_template_language": "not-supported"}
        )
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "category_template_language"]
        assert "input" not in response.json()["detail"][0]
        assert str(PAYLOAD["master_password"]) not in response.text
        assert client.get("/api/v1/setup/status").json() == {"initialized": False}
        assert client.post("/api/v1/setup", json=PAYLOAD).status_code == 201


def test_localized_category_failure_rolls_back_owner_and_settings(
    postgres_database_settings: Settings,
) -> None:
    app = create_app(postgres_database_settings)
    with TestClient(app, raise_server_exceptions=False) as client:
        with patch(
            "app.application.setup.create_onboarding_categories",
            side_effect=RuntimeError("template failure"),
        ):
            assert (
                client.post(
                    "/api/v1/setup", json={**PAYLOAD, "category_template_language": "en"}
                ).status_code
                == 500
            )
        assert client.get("/api/v1/setup/status").json() == {"initialized": False}
        factory = create_session_factory(create_database_engine(postgres_database_settings))
        with factory() as session:
            assert session.scalar(select(OwnerCredential)) is None
            assert session.scalar(select(ApplicationSettings)) is None
            assert session.scalar(select(Category)) is None
        assert (
            client.post(
                "/api/v1/setup", json={**PAYLOAD, "category_template_language": "en"}
            ).status_code
            == 201
        )
