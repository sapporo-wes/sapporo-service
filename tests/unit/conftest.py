import json
import logging
import os
import sys
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from sapporo.config import AppConfig


# === Autouse fixtures (function scope, no state sharing) ===


@pytest.fixture(autouse=True)
def _clean_argv() -> Generator[None, None, None]:
    original_argv = sys.argv[:]
    sys.argv = ["sapporo"]

    yield

    sys.argv = original_argv


@pytest.fixture(autouse=True)
def _clean_sapporo_env() -> Generator[None, None, None]:
    original_env = {k: v for k, v in os.environ.items() if k.startswith("SAPPORO_")}
    for k in original_env:
        del os.environ[k]

    yield

    for k in list(os.environ):
        if k.startswith("SAPPORO_"):
            del os.environ[k]
    for k, v in original_env.items():
        os.environ[k] = v


@pytest.fixture(autouse=True)
def _clear_all_caches() -> Generator[None, None, None]:
    _do_clear_caches()

    yield

    _do_clear_caches()


def _do_clear_caches() -> None:
    from sapporo.auth import fetch_endpoint_metadata, fetch_jwks, get_auth_config
    from sapporo.config import get_config
    from sapporo.database import create_db_engine
    from sapporo.factory import create_executable_wfs, create_service_info

    get_config.cache_clear()
    create_service_info.cache_clear()
    create_executable_wfs.cache_clear()
    get_auth_config.cache_clear()
    fetch_endpoint_metadata.cache_clear()
    fetch_jwks.cache_clear()
    create_db_engine.cache_clear()


# === Helper functions ===


def mock_get_config(mocker: "MockerFixture", app_config: "AppConfig") -> None:
    mocker.patch("sapporo.app.get_config", return_value=app_config)
    mocker.patch("sapporo.auth.get_config", return_value=app_config)
    mocker.patch("sapporo.config.get_config", return_value=app_config)
    mocker.patch("sapporo.database.get_config", return_value=app_config)
    mocker.patch("sapporo.factory.get_config", return_value=app_config)
    mocker.patch("sapporo.run.get_config", return_value=app_config)
    mocker.patch("sapporo.validator.get_config", return_value=app_config)


def default_auth_config_dict() -> dict[str, Any]:
    from argon2 import PasswordHasher

    ph = PasswordHasher()
    password_hash = ph.hash("sapporo-test-password")

    return {
        "auth_enabled": False,
        "idp_provider": "sapporo",
        "sapporo_auth_config": {
            "secret_key": "sapporo_test_secret_key_for_unit_tests",
            "expires_delta_hours": 24,
            "users": [{"username": "test-user", "password_hash": password_hash}],
        },
        "external_config": {
            "idp_url": "https://example.com/realms/test",
            "jwt_audience": "account",
            "client_mode": "public",
            "client_id": "test-client",
            "client_secret": "test-secret",
        },
    }


def write_auth_config(directory: Path, config_dict: dict[str, Any]) -> Path:
    auth_config_path = directory.joinpath("auth_config.json")
    auth_config_path.write_text(json.dumps(config_dict), encoding="utf-8")

    return auth_config_path


def create_test_client(
    mocker: "MockerFixture",
    tmp_dir: Path,
    app_config: "AppConfig | None" = None,
) -> TestClient:
    from sapporo.config import AppConfig

    resolved_config: AppConfig
    if app_config is None:
        resolved_config = AppConfig(run_dir=tmp_dir)
    else:
        app_config.run_dir = tmp_dir
        resolved_config = app_config
    mock_get_config(mocker, resolved_config)
    _do_clear_caches()

    from sapporo.database import init_db

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    init_db()

    from sapporo.app import create_app

    return TestClient(create_app())
