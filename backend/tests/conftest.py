import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql

from app.core.config import AppEnvironment, Settings, get_settings
from app.main import create_app

BACKEND_DIR = Path(__file__).parents[1]


@pytest.fixture
def application() -> FastAPI:
    return create_app(
        Settings(
            app_env=AppEnvironment.TEST,
            database_name="hermes_test",
            database_password="test-only-password",
        )
    )


@pytest.fixture
def client(application: FastAPI) -> Iterator[TestClient]:
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def postgres_database_settings() -> Iterator[Settings]:
    """Create a disposable migrated PostgreSQL database when explicitly enabled."""
    if os.getenv("HERMES_TEST_POSTGRES") != "1":
        pytest.skip("set HERMES_TEST_POSTGRES=1 to run PostgreSQL integration tests")

    host = os.getenv("HERMES_TEST_DATABASE_HOST", "127.0.0.1")
    port = int(os.getenv("HERMES_TEST_DATABASE_PORT", "5432"))
    user = os.getenv("HERMES_TEST_DATABASE_USER", "hermes")
    password = os.getenv("HERMES_TEST_DATABASE_PASSWORD", "test-only-password")
    database_name = f"hermes_test_{uuid4().hex}"

    try:
        admin_connection = psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname="postgres",
            autocommit=True,
        )
    except psycopg.OperationalError as error:
        pytest.fail(f"PostgreSQL test server is unavailable: {error}")

    with admin_connection:
        admin_connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )

    environment = {
        "HERMES_APP_ENV": "test",
        "HERMES_DATABASE_HOST": host,
        "HERMES_DATABASE_PORT": str(port),
        "HERMES_DATABASE_NAME": database_name,
        "HERMES_DATABASE_USER": user,
        "HERMES_DATABASE_PASSWORD": password,
    }
    previous = {key: os.environ.get(key) for key in environment}
    os.environ.update(environment)
    get_settings.cache_clear()
    try:
        command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
        yield Settings(
            app_env=AppEnvironment.TEST,
            database_host=host,
            database_port=port,
            database_name=database_name,
            database_user=user,
            database_password=password,
            login_admission_interval_ms=0,
        )
    finally:
        get_settings.cache_clear()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        with psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname="postgres",
            autocommit=True,
        ) as cleanup_connection:
            cleanup_connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )
