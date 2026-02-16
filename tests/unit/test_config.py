import os
import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sapporo.config import PKG_DIR, AppConfig, get_config

# === AppConfig defaults ===


def test_app_config_default_host() -> None:
    config = AppConfig()
    # Inside docker or not, it should be a valid host
    assert config.host in ("0.0.0.0", "127.0.0.1")


def test_app_config_default_port() -> None:
    assert AppConfig().port == 1122


def test_app_config_default_debug_is_false() -> None:
    assert AppConfig().debug is False


def test_app_config_default_run_dir() -> None:
    assert AppConfig().run_dir == Path.cwd().joinpath("runs")


def test_app_config_default_service_info() -> None:
    assert AppConfig().service_info == PKG_DIR.joinpath("service_info.json")


def test_app_config_default_executable_workflows() -> None:
    assert AppConfig().executable_workflows == PKG_DIR.joinpath("executable_workflows.json")


def test_app_config_default_run_sh() -> None:
    assert AppConfig().run_sh == PKG_DIR.joinpath("run.sh")


def test_app_config_default_url_prefix_is_empty() -> None:
    assert AppConfig().url_prefix == ""


def test_app_config_default_allow_origin_is_star() -> None:
    assert AppConfig().allow_origin == "*"


def test_app_config_default_auth_config() -> None:
    assert AppConfig().auth_config == PKG_DIR.joinpath("auth_config.json")


def test_app_config_default_run_remove_older_than_days_is_none() -> None:
    assert AppConfig().run_remove_older_than_days is None


def test_app_config_default_base_url() -> None:
    config = AppConfig()
    assert config.base_url == f"http://{config.host}:1122"


# === get_config priority: CLI > env > default ===


@pytest.mark.parametrize(
    ("arg_name", "arg_value", "attr_name", "expected"),
    [
        ("--host", "0.0.0.0", "host", "0.0.0.0"),
        ("--port", "8080", "port", 8080),
        ("--run-dir", "/tmp/runs", "run_dir", Path("/tmp/runs")),
        ("--service-info", "/tmp/si.json", "service_info", Path("/tmp/si.json")),
        ("--executable-workflows", "/tmp/ew.json", "executable_workflows", Path("/tmp/ew.json")),
        ("--run-sh", "/tmp/run.sh", "run_sh", Path("/tmp/run.sh")),
        ("--url-prefix", "/api", "url_prefix", "/api"),
        ("--base-url", "http://example.com", "base_url", "http://example.com"),
        ("--allow-origin", "http://example.com", "allow_origin", "http://example.com"),
        ("--auth-config", "/tmp/ac.json", "auth_config", Path("/tmp/ac.json")),
        ("--run-remove-older-than-days", "30", "run_remove_older_than_days", 30),
    ],
)
def test_get_config_with_cli_args(arg_name: str, arg_value: str, attr_name: str, expected: object) -> None:
    if arg_value is not None:
        sys.argv = ["sapporo", arg_name, arg_value]
    else:
        sys.argv = ["sapporo", arg_name]
    config = get_config()
    assert getattr(config, attr_name) == expected


def test_get_config_with_debug_flag() -> None:
    sys.argv = ["sapporo", "--debug"]
    config = get_config()
    assert config.debug is True


@pytest.mark.parametrize(
    ("env_var", "value", "attr_name", "expected"),
    [
        ("SAPPORO_HOST", "0.0.0.0", "host", "0.0.0.0"),
        ("SAPPORO_PORT", "8080", "port", 8080),
        ("SAPPORO_DEBUG", "true", "debug", True),
        ("SAPPORO_RUN_DIR", "/tmp/runs", "run_dir", Path("/tmp/runs")),
        ("SAPPORO_SERVICE_INFO", "/tmp/si.json", "service_info", Path("/tmp/si.json")),
        ("SAPPORO_EXECUTABLE_WORKFLOWS", "/tmp/ew.json", "executable_workflows", Path("/tmp/ew.json")),
        ("SAPPORO_RUN_SH", "/tmp/run.sh", "run_sh", Path("/tmp/run.sh")),
        ("SAPPORO_URL_PREFIX", "/api", "url_prefix", "/api"),
        ("SAPPORO_BASE_URL", "http://example.com", "base_url", "http://example.com"),
        ("SAPPORO_ALLOW_ORIGIN", "http://example.com", "allow_origin", "http://example.com"),
        ("SAPPORO_AUTH_CONFIG", "/tmp/ac.json", "auth_config", Path("/tmp/ac.json")),
        ("SAPPORO_RUN_REMOVE_OLDER_THAN_DAYS", "30", "run_remove_older_than_days", 30),
    ],
)
def test_get_config_with_env_vars(env_var: str, value: str, attr_name: str, expected: object) -> None:
    os.environ[env_var] = value
    config = get_config()
    assert getattr(config, attr_name) == expected


# === run_remove_older_than_days boundary values ===


def test_get_config_run_remove_older_than_days_zero_raises_value_error() -> None:
    sys.argv = ["sapporo", "--run-remove-older-than-days", "0"]
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        get_config()


def test_get_config_run_remove_older_than_days_negative_raises_value_error() -> None:
    sys.argv = ["sapporo", "--run-remove-older-than-days", "-1"]
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        get_config()


def test_get_config_run_remove_older_than_days_one_succeeds() -> None:
    sys.argv = ["sapporo", "--run-remove-older-than-days", "1"]
    config = get_config()
    assert config.run_remove_older_than_days == 1


@given(st.integers(min_value=1, max_value=10000))
def test_get_config_run_remove_older_than_days_positive_int_accepted(days: int) -> None:
    get_config.cache_clear()
    sys.argv = ["sapporo", "--run-remove-older-than-days", str(days)]
    config = get_config()
    assert config.run_remove_older_than_days == days
