import json
import logging
import os
import sys
from collections.abc import Generator
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck
from hypothesis import settings as hypothesis_settings
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile as StarletteUploadFile

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from sapporo.config import AppConfig


# === mutmut compatibility ===


hypothesis_settings.register_profile(
    "mutmut",
    suppress_health_check=[HealthCheck.differing_executors],
)


def pytest_configure(config: pytest.Config) -> None:
    """Set up mutmut-specific workarounds when running inside the mutants directory.

    mutmut v3 copies only Python source files to ``mutants/`` and applies
    mutations there.  Two adjustments are needed:

    1. **Data-file symlinks** -Package data files (``.yml``, ``.json``,
       ``.sh``) are not copied, causing ``FileNotFoundError`` when modules
       resolve them via ``importlib.resources.files()``.  This hook creates
       symlinks from the original package directory.
    2. **Hypothesis profile** -mutmut wraps every function with a trampoline,
       which triggers Hypothesis's ``differing_executors`` health check.  The
       ``mutmut`` profile suppresses this check.
    """
    cwd = Path.cwd()
    if cwd.name != "mutants":
        return
    mutants_sapporo = cwd / "sapporo"
    real_sapporo = cwd.parent / "sapporo"
    if mutants_sapporo.is_dir() and real_sapporo.is_dir():
        for src in real_sapporo.iterdir():
            if src.is_file() and src.suffix != ".py":
                dst = mutants_sapporo / src.name
                if not dst.exists():
                    dst.symlink_to(src)
    hypothesis_settings.load_profile("mutmut")


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
    from sapporo.config import _load_ga4gh_wes_spec, _load_pkg_dir, get_config
    from sapporo.database import create_db_engine
    from sapporo.factory import create_executable_wfs, create_service_info

    get_config.cache_clear()
    _load_pkg_dir.cache_clear()
    _load_ga4gh_wes_spec.cache_clear()
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


# === Run directory helper ===


def create_run_dir(
    run_dir: Path,
    run_id: str,
    state: str = "COMPLETE",
    start_time: str | None = None,
    end_time: str | None = None,
    run_request_dict: dict[str, Any] | None = None,
    username: str | None = None,
    tags: dict[str, str] | None = None,
    exit_code: str | None = None,
    cmd: str | None = None,
    stdout_content: str | None = None,
    stderr_content: str | None = None,
    wf_params: str | None = None,
    outputs_json: list[dict[str, str]] | None = None,
    output_files: dict[str, str | bytes] | None = None,
    system_logs_content: str | None = None,
    wf_engine_params_content: str | None = None,
) -> Path:
    """Create a run directory structure under run_dir following RUN_DIR_STRUCTURE."""
    from sapporo.config import RUN_DIR_STRUCTURE
    from sapporo.utils import now_str

    rd = run_dir / run_id[:2] / run_id
    rd.mkdir(parents=True, exist_ok=True)
    rd.joinpath(RUN_DIR_STRUCTURE["exe_dir"]).mkdir(parents=True, exist_ok=True)
    rd.joinpath(RUN_DIR_STRUCTURE["outputs_dir"]).mkdir(parents=True, exist_ok=True)

    rd.joinpath(RUN_DIR_STRUCTURE["state"]).write_text(state, encoding="utf-8")
    rd.joinpath(RUN_DIR_STRUCTURE["start_time"]).write_text(start_time or now_str(), encoding="utf-8")
    if end_time is not None:
        rd.joinpath(RUN_DIR_STRUCTURE["end_time"]).write_text(end_time, encoding="utf-8")

    request = run_request_dict or {
        "workflow_params": "{}",
        "workflow_type": "CWL",
        "workflow_type_version": "v1.0",
        "tags": tags or {},
        "workflow_engine": "cwltool",
        "workflow_engine_version": None,
        "workflow_engine_parameters": None,
        "workflow_url": "https://example.com/wf.cwl",
        "workflow_attachment": [],
        "workflow_attachment_obj": [],
    }
    rd.joinpath(RUN_DIR_STRUCTURE["run_request"]).write_text(json.dumps(request, indent=2), encoding="utf-8")

    runtime_info = {"sapporo_version": "test", "base_url": "http://localhost:1122"}
    rd.joinpath(RUN_DIR_STRUCTURE["runtime_info"]).write_text(json.dumps(runtime_info, indent=2), encoding="utf-8")

    rd.joinpath(RUN_DIR_STRUCTURE["system_logs"]).write_text(
        system_logs_content if system_logs_content is not None else "[]", encoding="utf-8"
    )

    if username is not None:
        rd.joinpath(RUN_DIR_STRUCTURE["username"]).write_text(username, encoding="utf-8")

    if exit_code is not None:
        rd.joinpath(RUN_DIR_STRUCTURE["exit_code"]).write_text(exit_code, encoding="utf-8")

    if cmd is not None:
        rd.joinpath(RUN_DIR_STRUCTURE["cmd"]).write_text(cmd, encoding="utf-8")

    if stdout_content is not None:
        rd.joinpath(RUN_DIR_STRUCTURE["stdout"]).write_text(stdout_content, encoding="utf-8")

    if stderr_content is not None:
        rd.joinpath(RUN_DIR_STRUCTURE["stderr"]).write_text(stderr_content, encoding="utf-8")

    if wf_params is not None:
        rd.joinpath(RUN_DIR_STRUCTURE["wf_params"]).write_text(wf_params, encoding="utf-8")

    if wf_engine_params_content is not None:
        rd.joinpath(RUN_DIR_STRUCTURE["wf_engine_params"]).write_text(wf_engine_params_content, encoding="utf-8")

    if outputs_json is not None:
        rd.joinpath(RUN_DIR_STRUCTURE["outputs"]).write_text(json.dumps(outputs_json), encoding="utf-8")

    if output_files is not None:
        for file_name, content in output_files.items():
            out_path = rd.joinpath(RUN_DIR_STRUCTURE["outputs_dir"], file_name)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                out_path.write_bytes(content)
            else:
                out_path.write_text(content, encoding="utf-8")

    return rd


def make_run_request_form(
    workflow_params: str = "{}",
    workflow_type: str = "CWL",
    workflow_type_version: str = "v1.0",
    workflow_engine: str = "cwltool",
    workflow_url: str = "https://example.com/wf.cwl",
    workflow_attachment: list[StarletteUploadFile] | None = None,
    workflow_attachment_obj: list[dict[str, str]] | None = None,
    tags: dict[str, str] | None = None,
    workflow_engine_parameters: dict[str, str] | None = None,
) -> Any:
    """Create a minimal RunRequestForm for testing."""
    from sapporo.schemas import FileObject, RunRequestForm

    attachments = workflow_attachment or []
    attachment_objs = [FileObject(**obj) for obj in (workflow_attachment_obj or [])]

    return RunRequestForm(
        workflow_params=workflow_params,
        workflow_type=workflow_type,
        workflow_type_version=workflow_type_version,
        tags=tags or {},
        workflow_engine=workflow_engine,
        workflow_engine_version=None,
        workflow_engine_parameters=workflow_engine_parameters,
        workflow_url=workflow_url,
        workflow_attachment=attachments,
        workflow_attachment_obj=attachment_objs,
    )


def make_upload_file(filename: str, content: bytes = b"test content") -> StarletteUploadFile:
    """Create an UploadFile for testing."""
    return StarletteUploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": "application/octet-stream"}),
    )
