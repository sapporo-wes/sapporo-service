import contextlib
import logging
import os
import shutil
import sys
import tempfile
from collections.abc import Generator
from functools import cache
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from httpx._types import RequestFiles

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from sapporo.config import AppConfig


@cache
def package_root() -> Path:
    root = Path(__file__).parent
    while not root.joinpath("pyproject.toml").exists():
        root = root.parent
    return root


@pytest.fixture(scope="session", autouse=True)
def reset_argv() -> Generator[None, None, None]:
    original_argv = sys.argv[:]
    sys.argv = ["sapporo"]

    yield

    sys.argv = original_argv


@pytest.fixture(scope="session", autouse=True)
def reset_os_env() -> Generator[None, None, None]:
    original_os_env = {k: v for k, v in os.environ.items() if k.startswith("SAPPORO_")}
    keys = original_os_env.keys()
    for k in keys:
        del os.environ[k]

    yield

    for k in keys:
        os.environ[k] = original_os_env[k]


@pytest.fixture
def tmpdir() -> Generator[Path, None, None]:
    tempdir = tempfile.mkdtemp()
    yield Path(tempdir)
    with contextlib.suppress(Exception):
        shutil.rmtree(tempdir)


@pytest.fixture(scope="function", autouse=True)
def clear_cache_fixture() -> None:
    clear_cache()


def clear_cache() -> None:
    from sapporo.config import get_config

    get_config.cache_clear()

    from sapporo.factory import create_executable_wfs, create_service_info

    create_service_info.cache_clear()
    create_executable_wfs.cache_clear()

    from sapporo.auth import fetch_endpoint_metadata, fetch_jwks, get_auth_config

    get_auth_config.cache_clear()
    fetch_endpoint_metadata.cache_clear()
    fetch_jwks.cache_clear()

    from sapporo.database import create_db_engine

    create_db_engine.cache_clear()


def mock_get_config(mocker: "MockerFixture", app_config: "AppConfig") -> None:
    mocker.patch("sapporo.app.get_config", return_value=app_config)
    mocker.patch("sapporo.auth.get_config", return_value=app_config)
    mocker.patch("sapporo.config.get_config", return_value=app_config)
    mocker.patch("sapporo.database.get_config", return_value=app_config)
    mocker.patch("sapporo.factory.get_config", return_value=app_config)
    mocker.patch("sapporo.run.get_config", return_value=app_config)
    mocker.patch("sapporo.validator.get_config", return_value=app_config)


def anyhow_get_test_client(
    app_config: "AppConfig | None",
    mocker: "MockerFixture",
    tmpdir: Path,
) -> TestClient:
    """Create a test client with proper configuration, mocking, and database initialization.

    To perform a proper test, it is necessary to set the run directory in the app_config to a temporary directory,
    mock the get_config function, and initialize the database. Without following these steps and calling create_app(),
    errors often occur due to caching issues and other problems.
    This function handles all these tedious steps at once, making it easier to get a test client for testing purposes.

    It could have been a fixture, but next time, the order problem of the fixture will occur, so I defined it as a function.
    """
    from sapporo.config import AppConfig

    resolved_config: AppConfig
    if app_config is None:
        resolved_config = AppConfig(run_dir=tmpdir)
    else:
        app_config.run_dir = tmpdir
        resolved_config = app_config
    mock_get_config(mocker, resolved_config)
    clear_cache()

    from sapporo.database import init_db

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    init_db()

    from sapporo.app import create_app

    return TestClient(create_app())


def post_run(
    client: TestClient,
    workflow_type: str,
    workflow_engine: str,
    workflow_params: str | None = None,
    workflow_type_version: str | None = None,
    tags: str | None = None,
    workflow_engine_version: str | None = None,
    workflow_engine_parameters: str | None = None,
    workflow_url: str | None = None,
    workflow_attachment: RequestFiles | None = None,
    workflow_attachment_obj: str | None = None,
) -> Response:
    data_raw: dict[str, str | None] = {
        "workflow_params": workflow_params,
        "workflow_type": workflow_type,
        "workflow_type_version": workflow_type_version,
        "tags": tags,
        "workflow_engine": workflow_engine,
        "workflow_engine_version": workflow_engine_version,
        "workflow_engine_parameters": workflow_engine_parameters,
        "workflow_url": workflow_url,
        "workflow_attachment_obj": workflow_attachment_obj,
    }
    data: dict[str, str] = {k: v for k, v in data_raw.items() if v is not None}

    response: Response = client.post("/runs", data=data, files=workflow_attachment)
    return response


def wait_for_run(client: TestClient, run_id: str) -> str:
    count = 0
    state: str = ""
    while count <= 120:
        sleep(3)
        response = client.get(f"/runs/{run_id}")
        state = str(response.json()["state"])
        if state in ["COMPLETE", "EXECUTOR_ERROR", "SYSTEM_ERROR", "CANCELED", "DELETED"]:
            break
        count += 1
    if count > 120:
        msg = "The run did not complete within the expected time."
        raise TimeoutError(msg)

    return state


def assert_run_complete(run_id: str, data: dict[str, Any]) -> None:
    assert data["run_id"] == run_id
    assert data["state"] == "COMPLETE"
    assert data["run_log"]["cmd"] is not None
    assert data["run_log"]["start_time"] is not None
    assert data["run_log"]["end_time"] is not None
    assert data["run_log"]["stdout"] is not None
    assert data["run_log"]["stderr"] is not None
    assert data["run_log"]["exit_code"] == 0
