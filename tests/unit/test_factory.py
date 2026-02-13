import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

from sapporo.config import RUN_DIR_STRUCTURE
from sapporo.factory import create_executable_wfs, create_service_info
from sapporo.schemas import State

from .conftest import mock_get_config

# === create_service_info ===


def test_create_service_info_reads_file_and_returns_service_info(mocker: "MockerFixture", tmp_path: Path) -> None:
    service_info_data = {
        "workflow_type_versions": {"CWL": {"workflow_type_version": ["v1.0"]}},
        "workflow_engine_versions": {"cwltool": {"workflow_engine_version": ["3.1"]}},
    }
    service_info_path = tmp_path.joinpath("service_info.json")
    service_info_path.write_text(json.dumps(service_info_data), encoding="utf-8")

    from sapporo.config import AppConfig

    app_config = AppConfig(service_info=service_info_path)
    mock_get_config(mocker, app_config)

    result = create_service_info()
    assert "CWL" in result.workflow_type_versions
    assert "cwltool" in result.workflow_engine_versions


def test_create_service_info_uses_defaults_for_missing_fields(mocker: "MockerFixture", tmp_path: Path) -> None:
    service_info_path = tmp_path.joinpath("service_info.json")
    service_info_path.write_text("{}", encoding="utf-8")

    from sapporo.config import AppConfig

    app_config = AppConfig(service_info=service_info_path)
    mock_get_config(mocker, app_config)

    result = create_service_info()
    assert result.id == "sapporo-service"
    assert result.name == "sapporo-service"
    assert result.supported_wes_versions == ["1.1.0", "sapporo-wes-2.0.0"]


def test_create_service_info_is_cached(mocker: "MockerFixture", tmp_path: Path) -> None:
    service_info_path = tmp_path.joinpath("service_info.json")
    service_info_path.write_text("{}", encoding="utf-8")

    from sapporo.config import AppConfig

    app_config = AppConfig(service_info=service_info_path)
    mock_get_config(mocker, app_config)

    result1 = create_service_info()
    result2 = create_service_info()
    assert result1 is result2


# === create_executable_wfs ===


def test_create_executable_wfs_reads_existing_file(mocker: "MockerFixture", tmp_path: Path) -> None:
    ewf_data = {"workflows": ["https://example.com/wf.cwl"]}
    ewf_path = tmp_path.joinpath("executable_workflows.json")
    ewf_path.write_text(json.dumps(ewf_data), encoding="utf-8")

    from sapporo.config import AppConfig

    app_config = AppConfig(executable_workflows=ewf_path)
    mock_get_config(mocker, app_config)

    result = create_executable_wfs()
    assert result.workflows == ["https://example.com/wf.cwl"]


def test_create_executable_wfs_returns_empty_when_file_missing(mocker: "MockerFixture", tmp_path: Path) -> None:
    ewf_path = tmp_path.joinpath("nonexistent.json")

    from sapporo.config import AppConfig

    app_config = AppConfig(executable_workflows=ewf_path)
    mock_get_config(mocker, app_config)

    result = create_executable_wfs()
    assert result.workflows == []


def test_create_executable_wfs_is_cached(mocker: "MockerFixture", tmp_path: Path) -> None:
    ewf_path = tmp_path.joinpath("nonexistent.json")

    from sapporo.config import AppConfig

    app_config = AppConfig(executable_workflows=ewf_path)
    mock_get_config(mocker, app_config)

    result1 = create_executable_wfs()
    result2 = create_executable_wfs()
    assert result1 is result2


# === create_run_log / create_run_status / create_run_summary ===

# Helper to create a minimal run directory structure


def _create_run_dir(tmp_path: Path, run_id: str, state: str = "COMPLETE") -> Path:
    run_dir = tmp_path.joinpath(run_id[:2]).joinpath(run_id)
    run_dir.mkdir(parents=True)

    run_dir.joinpath(RUN_DIR_STRUCTURE["state"]).write_text(state, encoding="utf-8")

    return run_dir


def test_create_run_status_returns_state(mocker: "MockerFixture", tmp_path: Path) -> None:
    from sapporo.config import AppConfig
    from sapporo.factory import create_run_status

    app_config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, app_config)

    run_id = "abcd1234-5678-9012-3456-789012345678"
    _create_run_dir(tmp_path, run_id, "RUNNING")

    status = create_run_status(run_id)
    assert status.run_id == run_id
    assert status.state == State.RUNNING


def test_create_run_status_returns_unknown_when_no_state_file(mocker: "MockerFixture", tmp_path: Path) -> None:
    from sapporo.config import AppConfig
    from sapporo.factory import create_run_status

    app_config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, app_config)

    run_id = "abcd1234-5678-9012-3456-789012345678"
    run_dir = tmp_path.joinpath(run_id[:2]).joinpath(run_id)
    run_dir.mkdir(parents=True)

    status = create_run_status(run_id)
    assert status.state == State.UNKNOWN


def test_create_run_summary_with_minimal_run_dir(mocker: "MockerFixture", tmp_path: Path) -> None:
    from sapporo.config import AppConfig
    from sapporo.factory import create_run_summary

    app_config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, app_config)

    run_id = "abcd1234-5678-9012-3456-789012345678"
    run_dir = _create_run_dir(tmp_path, run_id, "COMPLETE")
    run_dir.joinpath(RUN_DIR_STRUCTURE["start_time"]).write_text("2024-01-15T10:30:00Z", encoding="utf-8")
    run_dir.joinpath(RUN_DIR_STRUCTURE["end_time"]).write_text("2024-01-15T10:35:00Z", encoding="utf-8")

    summary = create_run_summary(run_id)
    assert summary.run_id == run_id
    assert summary.state == State.COMPLETE
    assert summary.start_time == "2024-01-15T10:30:00Z"
    assert summary.end_time == "2024-01-15T10:35:00Z"
    assert summary.tags == {}


def test_create_run_log_with_minimal_run_dir(mocker: "MockerFixture", tmp_path: Path) -> None:
    from sapporo.config import AppConfig
    from sapporo.factory import create_run_log

    app_config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, app_config)

    run_id = "abcd1234-5678-9012-3456-789012345678"
    run_dir = _create_run_dir(tmp_path, run_id, "COMPLETE")
    run_dir.joinpath(RUN_DIR_STRUCTURE["start_time"]).write_text("2024-01-15T10:30:00Z", encoding="utf-8")
    run_dir.joinpath(RUN_DIR_STRUCTURE["end_time"]).write_text("2024-01-15T10:35:00Z", encoding="utf-8")
    run_dir.joinpath(RUN_DIR_STRUCTURE["exit_code"]).write_text("0", encoding="utf-8")

    run_log = create_run_log(run_id)
    assert run_log.run_id == run_id
    assert run_log.state == State.COMPLETE
    assert run_log.run_log is not None
    assert run_log.run_log.start_time == "2024-01-15T10:30:00Z"
    assert run_log.run_log.end_time == "2024-01-15T10:35:00Z"
    assert run_log.run_log.exit_code == 0
