import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

from sapporo.schemas import (
    Organization,
    ServiceInfo,
    ServiceType,
    WorkflowEngineVersion,
    WorkflowTypeVersion,
)
from sapporo.validator import (
    validate_run_id,
    validate_wf_engine_type_and_version,
    validate_wf_type_and_version,
)

from .conftest import mock_get_config


def _make_service_info() -> ServiceInfo:
    return ServiceInfo(
        id="test",
        name="test",
        type=ServiceType(group="org.ga4gh", artifact="wes", version="1.1.0"),
        organization=Organization(name="Test", url="https://example.com"),
        version="1.0.0",
        workflow_type_versions={
            "CWL": WorkflowTypeVersion(workflow_type_version=["v1.0", "v1.1"]),
            "WDL": WorkflowTypeVersion(workflow_type_version=["1.0"]),
        },
        supported_wes_versions=["1.1.0"],
        supported_filesystem_protocols=["http"],
        workflow_engine_versions={
            "cwltool": WorkflowEngineVersion(workflow_engine_version=["3.1"]),
            "nextflow": WorkflowEngineVersion(workflow_engine_version=["22.04"]),
        },
        default_workflow_engine_parameters={},
        system_state_counts={},
        auth_instructions_url="https://example.com/auth",
        tags={},
    )


# === validate_wf_type_and_version ===


def test_validate_wf_type_and_version_with_valid_type_and_version(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    wf_type, wf_version = validate_wf_type_and_version("CWL", "v1.0")
    assert wf_type == "CWL"
    assert wf_version == "v1.0"


def test_validate_wf_type_and_version_with_invalid_type_raises_400(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    with pytest.raises(HTTPException) as exc_info:
        validate_wf_type_and_version("INVALID", "v1.0")
    assert exc_info.value.status_code == 400


def test_validate_wf_type_and_version_with_none_version_returns_first(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    wf_type, wf_version = validate_wf_type_and_version("CWL", None)
    assert wf_type == "CWL"
    assert wf_version == "v1.0"


# === validate_wf_engine_type_and_version ===


def test_validate_wf_engine_type_and_version_with_valid_engine(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    engine, version = validate_wf_engine_type_and_version("cwltool", "3.1")
    assert engine == "cwltool"
    assert version == "3.1"


def test_validate_wf_engine_type_and_version_with_invalid_engine_raises_400(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    with pytest.raises(HTTPException) as exc_info:
        validate_wf_engine_type_and_version("INVALID", "1.0")
    assert exc_info.value.status_code == 400


def test_validate_wf_engine_type_and_version_with_none_version_returns_first(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    engine, version = validate_wf_engine_type_and_version("cwltool", None)
    assert engine == "cwltool"
    assert version == "3.1"


# === validate_run_id ===


def test_validate_run_id_with_nonexistent_run_raises_404(mocker: "MockerFixture", tmp_path: Path) -> None:
    from sapporo.config import AppConfig

    app_config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, app_config)

    with pytest.raises(HTTPException) as exc_info:
        validate_run_id("nonexistent-run-id", None)
    assert exc_info.value.status_code == 404


def test_validate_run_id_with_existing_run_succeeds(mocker: "MockerFixture", tmp_path: Path) -> None:
    from sapporo.config import AppConfig

    app_config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, app_config)

    run_id = "abcd1234-5678-9012-3456-789012345678"
    run_dir = tmp_path.joinpath(run_id[:2]).joinpath(run_id)
    run_dir.mkdir(parents=True)

    validate_run_id(run_id, None)  # Should not raise


def test_validate_run_id_with_wrong_username_raises_403(mocker: "MockerFixture", tmp_path: Path) -> None:
    from sapporo.config import AppConfig

    app_config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, app_config)

    run_id = "abcd1234-5678-9012-3456-789012345678"
    run_dir = tmp_path.joinpath(run_id[:2]).joinpath(run_id)
    run_dir.mkdir(parents=True)

    # Write username file
    username_file = run_dir.joinpath("username.txt")
    username_file.write_text("owner-user", encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        validate_run_id(run_id, "other-user")
    assert exc_info.value.status_code == 403


def test_validate_run_id_with_none_username_skips_ownership_check(mocker: "MockerFixture", tmp_path: Path) -> None:
    from sapporo.config import AppConfig

    app_config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, app_config)

    run_id = "abcd1234-5678-9012-3456-789012345678"
    run_dir = tmp_path.joinpath(run_id[:2]).joinpath(run_id)
    run_dir.mkdir(parents=True)

    username_file = run_dir.joinpath("username.txt")
    username_file.write_text("owner-user", encoding="utf-8")

    validate_run_id(run_id, None)  # Should not raise even though username file exists


# === validate_run_request ===


def test_validate_run_request_with_invalid_json_params_raises_error(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=type("EWF", (), {"workflows": []})(),
    )

    from sapporo.validator import validate_run_request

    with pytest.raises(json.JSONDecodeError):
        validate_run_request(
            wf_params="{invalid json",
            wf_type="CWL",
            wf_type_version="v1.0",
            tags=None,
            wf_engine="cwltool",
            wf_engine_version="3.1",
            wf_engine_parameters=None,
            wf_url="https://example.com/wf.cwl",
            wf_attachment=[],
            wf_attachment_obj=None,
        )


def test_validate_run_request_with_restricted_wf_url_raises_400(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())

    from sapporo.schemas import ExecutableWorkflows

    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=ExecutableWorkflows(workflows=["https://allowed.com/wf.cwl"]),
    )

    from sapporo.validator import validate_run_request

    with pytest.raises(HTTPException) as exc_info:
        validate_run_request(
            wf_params=None,
            wf_type="CWL",
            wf_type_version="v1.0",
            tags=None,
            wf_engine="cwltool",
            wf_engine_version="3.1",
            wf_engine_parameters=None,
            wf_url="https://not-allowed.com/wf.cwl",
            wf_attachment=[],
            wf_attachment_obj=None,
        )
    assert exc_info.value.status_code == 400
