import logging
import os
import sys
from pathlib import Path

import pytest

from .conftest import anyhow_get_test_client


def test_get_config_defaults():  # type: ignore[no-untyped-def]
    from sapporo.config import PKG_DIR, get_config
    from sapporo.utils import inside_docker

    config = get_config()
    assert config.host == ("0.0.0.0" if inside_docker() else "127.0.0.1")
    assert config.port == 1122
    assert config.debug is False
    assert config.run_dir == Path.cwd().joinpath("runs")
    assert config.service_info == PKG_DIR.joinpath("service_info.json")
    assert config.executable_workflows == PKG_DIR.joinpath("executable_workflows.json")
    assert config.run_sh == PKG_DIR.joinpath("run.sh")
    assert config.url_prefix == ""
    assert config.base_url == f"http://{config.host}:1122"
    assert config.allow_origin == "*"
    assert config.auth_config == PKG_DIR.joinpath("auth_config.json")
    assert config.run_remove_older_than_days is None


@pytest.mark.parametrize(
    "arg_name,arg_value,expected",
    [
        ("--host", "0.0.0.0", "0.0.0.0"),
        ("--port", "8080", 8080),
        ("--debug", None, True),
        ("--run-dir", "/tmp/runs", Path("/tmp/runs")),
        ("--service-info", "/tmp/service_info.json", Path("/tmp/service_info.json")),
        ("--executable-workflows", "/tmp/executable_workflows.json", Path("/tmp/executable_workflows.json")),
        ("--run-sh", "/tmp/run.sh", Path("/tmp/run.sh")),
        ("--url-prefix", "/api", "/api"),
        ("--base-url", "http://example.com", "http://example.com"),
        ("--allow-origin", "http://example.com", "http://example.com"),
        ("--auth-config", "/tmp/auth_config.json", Path("/tmp/auth_config.json")),
        ("--run-remove-older-than-days", "30", 30),
    ],
)
def test_get_config_with_args(arg_name, arg_value, expected):  # type: ignore[no-untyped-def]
    from sapporo.config import get_config

    sys.argv = ["sapporo"]
    if arg_value is not None:
        sys.argv.extend([arg_name, arg_value])
    else:
        sys.argv.append(arg_name)

    config = get_config()
    attr_name = arg_name.removeprefix("--").replace("-", "_")
    assert getattr(config, attr_name) == expected


@pytest.mark.parametrize(
    "env_var,value,expected",
    [
        ("SAPPORO_HOST", "0.0.0.0", "0.0.0.0"),
        ("SAPPORO_PORT", "8080", 8080),
        ("SAPPORO_DEBUG", "true", True),
        ("SAPPORO_RUN_DIR", "/tmp/runs", Path("/tmp/runs")),
        ("SAPPORO_SERVICE_INFO", "/tmp/service_info.json", Path("/tmp/service_info.json")),
        ("SAPPORO_EXECUTABLE_WORKFLOWS", "/tmp/executable_workflows.json", Path("/tmp/executable_workflows.json")),
        ("SAPPORO_RUN_SH", "/tmp/run.sh", Path("/tmp/run.sh")),
        ("SAPPORO_URL_PREFIX", "/api", "/api"),
        ("SAPPORO_BASE_URL", "http://example.com", "http://example.com"),
        ("SAPPORO_ALLOW_ORIGIN", "http://example.com", "http://example.com"),
        ("SAPPORO_AUTH_CONFIG", "/tmp/auth_config.json", Path("/tmp/auth_config.json")),
        ("SAPPORO_RUN_REMOVE_OLDER_THAN_DAYS", "30", 30),
    ],
)
def test_get_config_with_env_vars(env_var, value, expected):  # type: ignore[no-untyped-def]
    from sapporo.config import get_config

    os.environ[env_var] = value
    config = get_config()
    attr_name = env_var.split("_", 1)[1].lower()
    assert getattr(config, attr_name) == expected
    os.environ.pop(env_var)


def test_init_app_state(mocker, tmpdir):  # type: ignore[no-untyped-def]
    _client = anyhow_get_test_client(None, mocker, tmpdir)  # for clear all cache and dependencies

    from sapporo.app import init_app_state

    logging.getLogger("sapporo").setLevel(logging.WARNING)
    init_app_state()  # no raise
