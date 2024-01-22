# coding: utf-8
# pylint: disable=unused-argument
from pathlib import Path
from typing import Any

import pytest
from pytest import MonkeyPatch

from sapporo.config import get_config, parse_args
from sapporo.const import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_URL_PREFIX


def test_default_params(delete_env_vars: None) -> None:
    args = parse_args([])
    config = get_config(args)

    assert config["host"] == DEFAULT_HOST
    assert config["port"] == DEFAULT_PORT
    assert config["debug"] is False
    assert config["get_runs"] is True
    assert config["workflow_attachment"] is True
    assert config["registered_only_mode"] is False
    assert config["url_prefix"] == DEFAULT_URL_PREFIX
    assert config["access_control_allow_origin"] == "*"


@pytest.mark.parametrize("env_var,value,expected_value", [
    ("SAPPORO_HOST", "127.0.0.1", "127.0.0.1"),
    ("SAPPORO_PORT", "8888", 8888),
    ("SAPPORO_DEBUG", "True", True),
    ("SAPPORO_RUN_DIR", "/test", Path("/test")),
    ("SAPPORO_SERVICE_INFO", "/test", Path("/test")),
    ("SAPPORO_EXECUTABLE_WORKFLOWS", "/test", Path("/test")),
    ("SAPPORO_GET_RUNS", "False", False),
    ("SAPPORO_WORKFLOW_ATTACHMENT", "False", False),
    ("SAPPORO_RUN_ONLY_REGISTERED_WORKFLOWS", "True", True),
    ("SAPPORO_URL_PREFIX", "/test", "/test"),
    ("SAPPORO_ACCESS_CONTROL_ALLOW_ORIGIN", "*", "*"),
])
def test_env_vars(env_var: str, value: str, expected_value: Any, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(env_var, value)
    args = parse_args([])
    config = get_config(args)

    assert config[env_var
                  .replace("SAPPORO_", "")
                  .replace("RUN_ONLY_REGISTERED_WORKFLOWS", "registered_only_mode").lower()] == expected_value  # type: ignore


def test_parse_args(delete_env_vars: None) -> None:
    args = parse_args(["--host", "127.0.0.1",
                       "--port", "8888",
                       "--debug",
                       "--run-dir", "/test",
                       "--disable-get-runs",
                       "--disable-workflow-attachment",
                       "--run-only-registered-workflows",
                       "--service-info", "/test",
                       "--executable-workflows", "/test",
                       "--run-sh", "/test",
                       "--url-prefix", "/test",])
    config = get_config(args)

    assert config["host"] == "127.0.0.1"
    assert config["port"] == 8888
    assert config["debug"] is True
    assert config["run_dir"] == Path("/test")
    assert config["get_runs"] is False
    assert config["workflow_attachment"] is False
    assert config["registered_only_mode"] is True
    assert config["service_info"] == Path("/test")
    assert config["executable_workflows"] == Path("/test")
    assert config["run_sh"] == Path("/test")
    assert config["url_prefix"] == "/test"
