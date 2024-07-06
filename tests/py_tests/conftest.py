# pylint: disable=C0415, W0613, W0621

import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient


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
    tempdir = tempfile.mkdtemp()
    yield Path(tempdir)
    try:
        shutil.rmtree(tempdir)
    except PermissionError:
        pass


@pytest.fixture(autouse=True)
def clear_get_config_cache():  # type: ignore
    from sapporo.config import get_config
    get_config.cache_clear()


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
    print(app_config)
    mock_get_config(mocker, app_config)  # type: ignore

    from sapporo.database import init_db
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    init_db()

    from sapporo.app import create_app
    return TestClient(create_app())
