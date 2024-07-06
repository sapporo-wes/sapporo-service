# pylint: disable=C0415, W0613, W0621

import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from time import sleep
from typing import Generator, Optional

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from httpx._types import RequestFiles


@pytest.fixture(scope="session", autouse=True)
def reset_argv() -> Generator[None, None, None]:
    original_argv = sys.argv[:]
    sys.argv = ["sapporo"]

    yield

    sys.argv = original_argv


@pytest.fixture(scope="session", autouse=True)
def reset_os_env() -> Generator[None, None, None]:
    original_os_env = os.environ.copy()
    os.environ.clear()

    yield

    os.environ.clear()
    os.environ.update(original_os_env)


@pytest.fixture()
def tmpdir() -> Generator[Path, None, None]:
    yield Path("/tmp/foobar")
    # tempdir = tempfile.mkdtemp()
    # yield Path(tempdir)
    # try:
    #     shutil.rmtree(tempdir)
    # except PermissionError:
    #     pass


@pytest.fixture(autouse=True)
def clear_cache():  # type: ignore
    from sapporo.config import get_config
    get_config.cache_clear()

    from sapporo.factory import create_executable_wfs, create_service_info
    create_service_info.cache_clear()
    create_executable_wfs.cache_clear()

    from sapporo.auth import (auth_depends_factory, fetch_endpoint_metadata,
                              fetch_jwks, get_auth_config,
                              is_create_token_endpoint_enabled)
    get_auth_config.cache_clear()
    auth_depends_factory.cache_clear()
    is_create_token_endpoint_enabled.cache_clear()
    fetch_endpoint_metadata.cache_clear()
    fetch_jwks.cache_clear()

    from sapporo.validator import (validate_wf_engine_type_and_version,
                                   validate_wf_type_and_version)
    validate_wf_type_and_version.cache_clear()
    validate_wf_engine_type_and_version.cache_clear()


def mock_get_config(mocker, app_config):  # type: ignore
    mocker.patch("sapporo.app.get_config", return_value=app_config)
    mocker.patch("sapporo.config.get_config", return_value=app_config)
    mocker.patch("sapporo.database.get_config", return_value=app_config)
    mocker.patch("sapporo.factory.get_config", return_value=app_config)
    mocker.patch("sapporo.run.get_config", return_value=app_config)
    mocker.patch("sapporo.validator.get_config", return_value=app_config)


def anyhow_get_test_client(app_config, mocker, tmpdir) -> TestClient:  # type: ignore
    """\
    To perform a proper test, it is necessary to set the run directory in the app_config to a temporary directory, mock the get_config function, and initialize the database. Without following these steps and calling create_app(), errors often occur due to caching issues and other problems.
    This function handles all these tedious steps at once, making it easier to get a test client for testing purposes.

    It could have been a fixture, but next time, the order problem of the fixture will occur, so I defined it as a function.
    """
    from sapporo.config import AppConfig
    if app_config is None:
        app_config = AppConfig(run_dir=tmpdir,)
    else:
        app_config.run_dir = tmpdir
    mock_get_config(mocker, app_config)  # type: ignore

    from sapporo.database import init_db
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    init_db()

    from sapporo.app import create_app
    return TestClient(create_app())


def post_run(
    client: TestClient,
    workflow_type: str,
    workflow_engine: str,
    workflow_params: Optional[str] = None,
    workflow_type_version: Optional[str] = None,
    tags: Optional[str] = None,
    workflow_engine_version: Optional[str] = None,
    workflow_engine_parameters: Optional[str] = None,
    workflow_url: Optional[str] = None,
    workflow_attachment: Optional[RequestFiles] = None,
    workflow_attachment_obj: Optional[str] = None,
) -> Response:
    data = {
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
    data = {k: v for k, v in data.items() if v is not None}

    return client.post("/runs", data=data, files=workflow_attachment)  # type: ignore


def wait_for_run_complete(client: TestClient, run_id: str) -> None:
    count = 0
    while count <= 120:
        sleep(3)
        response = client.get(f"/runs/{run_id}")
        if response.json()["state"] in ["COMPLETE", "EXECUTOR_ERROR", "SYSTEM_ERROR", "CANCELED", "DELETED"]:
            break
        count += 1
    if count > 120:
        raise TimeoutError("The run did not complete within the expected time.")
    if response.json()["state"] != "COMPLETE":
        raise RuntimeError(f"Run failed with state: {response.json()['state']}")
