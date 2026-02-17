import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

from sapporo.schemas import (
    ExecutableWorkflows,
    Organization,
    ServiceInfo,
    ServiceType,
    WorkflowEngineVersion,
    WorkflowTypeVersion,
)
from sapporo.validator import (
    validate_run_id,
    validate_run_request,
    validate_wf_engine_type_and_version,
    validate_wf_type_and_version,
)

from .conftest import mock_get_config


def _make_service_info(
    wf_type_versions: dict[str, WorkflowTypeVersion] | None = None,
    wf_engine_versions: dict[str, WorkflowEngineVersion] | None = None,
) -> ServiceInfo:
    return ServiceInfo(
        id="test",
        name="test",
        type=ServiceType(group="org.ga4gh", artifact="wes", version="1.1.0"),
        organization=Organization(name="Test", url="https://example.com"),
        version="1.0.0",
        workflow_type_versions=wf_type_versions
        or {
            "CWL": WorkflowTypeVersion(workflow_type_version=["v1.0", "v1.1"]),
            "WDL": WorkflowTypeVersion(workflow_type_version=["1.0"]),
        },
        supported_wes_versions=["1.1.0"],
        supported_filesystem_protocols=["http"],
        workflow_engine_versions=wf_engine_versions
        or {
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


def test_validate_wf_type_and_version_with_none_version_raises_400(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    with pytest.raises(HTTPException) as exc_info:
        validate_wf_type_and_version("CWL", None)
    assert exc_info.value.status_code == 400


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


def test_validate_wf_engine_type_and_version_with_none_version_returns_none(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    engine, version = validate_wf_engine_type_and_version("cwltool", None)
    assert engine == "cwltool"
    assert version is None


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


# === validate_run_request: normal cases ===


def test_validate_run_request_with_all_none_optionals_returns_defaults(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=ExecutableWorkflows(workflows=[]),
    )

    result = validate_run_request(
        wf_params=None,
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

    assert result.workflow_params == {}
    assert result.tags == {}
    assert result.workflow_engine_parameters is None
    assert result.workflow_url == "https://example.com/wf.cwl"
    assert result.workflow_attachment_obj == []
    assert result.workflow_attachment == []
    assert result.workflow_type == "CWL"
    assert result.workflow_type_version == "v1.0"
    assert result.workflow_engine == "cwltool"
    assert result.workflow_engine_version == "3.1"


def test_validate_run_request_with_json_strings_parses_correctly(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=ExecutableWorkflows(workflows=[]),
    )

    result = validate_run_request(
        wf_params='{"input": "file.txt"}',
        wf_type="CWL",
        wf_type_version="v1.0",
        tags='{"project": "genomics"}',
        wf_engine="cwltool",
        wf_engine_version="3.1",
        wf_engine_parameters='{"--debug": "true"}',
        wf_url="https://example.com/wf.cwl",
        wf_attachment=[],
        wf_attachment_obj='[{"file_name": "test.txt", "file_url": "https://example.com/test.txt"}]',
    )

    assert result.workflow_params == {"input": "file.txt"}
    assert result.tags == {"project": "genomics"}
    assert result.workflow_engine_parameters == {"--debug": "true"}
    assert result.workflow_url == "https://example.com/wf.cwl"
    assert len(result.workflow_attachment_obj) == 1
    assert result.workflow_attachment_obj[0].file_name == "test.txt"
    assert result.workflow_attachment_obj[0].file_url == "https://example.com/test.txt"


def test_validate_run_request_with_empty_executable_wfs_allows_any_url(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=ExecutableWorkflows(workflows=[]),
    )

    result = validate_run_request(
        wf_params=None,
        wf_type="CWL",
        wf_type_version="v1.0",
        tags=None,
        wf_engine="cwltool",
        wf_engine_version="3.1",
        wf_engine_parameters=None,
        wf_url="https://any-url.com/anything.cwl",
        wf_attachment=[],
        wf_attachment_obj=None,
    )

    assert result.workflow_url == "https://any-url.com/anything.cwl"


def test_validate_run_request_with_registered_wf_url_succeeds(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=ExecutableWorkflows(workflows=["https://registered.com/wf.cwl"]),
    )

    result = validate_run_request(
        wf_params=None,
        wf_type="CWL",
        wf_type_version="v1.0",
        tags=None,
        wf_engine="cwltool",
        wf_engine_version="3.1",
        wf_engine_parameters=None,
        wf_url="https://registered.com/wf.cwl",
        wf_attachment=[],
        wf_attachment_obj=None,
    )

    assert result.workflow_url == "https://registered.com/wf.cwl"


# === validate_run_request: JSON parse error cases ===


def test_validate_run_request_with_invalid_tags_json_raises_error(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=ExecutableWorkflows(workflows=[]),
    )

    with pytest.raises(json.JSONDecodeError):
        validate_run_request(
            wf_params=None,
            wf_type="CWL",
            wf_type_version="v1.0",
            tags="{invalid}",
            wf_engine="cwltool",
            wf_engine_version="3.1",
            wf_engine_parameters=None,
            wf_url="https://example.com/wf.cwl",
            wf_attachment=[],
            wf_attachment_obj=None,
        )


def test_validate_run_request_with_invalid_wf_engine_parameters_json_raises_error(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=ExecutableWorkflows(workflows=[]),
    )

    with pytest.raises(json.JSONDecodeError):
        validate_run_request(
            wf_params=None,
            wf_type="CWL",
            wf_type_version="v1.0",
            tags=None,
            wf_engine="cwltool",
            wf_engine_version="3.1",
            wf_engine_parameters="{not-json}",
            wf_url="https://example.com/wf.cwl",
            wf_attachment=[],
            wf_attachment_obj=None,
        )


def test_validate_run_request_with_invalid_wf_attachment_obj_json_raises_error(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=ExecutableWorkflows(workflows=[]),
    )

    with pytest.raises(json.JSONDecodeError):
        validate_run_request(
            wf_params=None,
            wf_type="CWL",
            wf_type_version="v1.0",
            tags=None,
            wf_engine="cwltool",
            wf_engine_version="3.1",
            wf_engine_parameters=None,
            wf_url="https://example.com/wf.cwl",
            wf_attachment=[],
            wf_attachment_obj="[not valid json",
        )


# === validate_run_request: required field rejection ===


def test_validate_run_request_with_none_workflow_url_raises_400(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=ExecutableWorkflows(workflows=[]),
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_run_request(
            wf_params=None,
            wf_type="CWL",
            wf_type_version="v1.0",
            tags=None,
            wf_engine="cwltool",
            wf_engine_version="3.1",
            wf_engine_parameters=None,
            wf_url=None,
            wf_attachment=[],
            wf_attachment_obj=None,
        )
    assert exc_info.value.status_code == 400


def test_validate_run_request_with_empty_workflow_url_raises_400(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=ExecutableWorkflows(workflows=[]),
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_run_request(
            wf_params=None,
            wf_type="CWL",
            wf_type_version="v1.0",
            tags=None,
            wf_engine="cwltool",
            wf_engine_version="3.1",
            wf_engine_parameters=None,
            wf_url="",
            wf_attachment=[],
            wf_attachment_obj=None,
        )
    assert exc_info.value.status_code == 400


def test_validate_run_request_with_none_workflow_type_version_raises_400(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())
    mocker.patch(
        "sapporo.validator.create_executable_wfs",
        return_value=ExecutableWorkflows(workflows=[]),
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_run_request(
            wf_params=None,
            wf_type="CWL",
            wf_type_version=None,
            tags=None,
            wf_engine="cwltool",
            wf_engine_version="3.1",
            wf_engine_parameters=None,
            wf_url="https://example.com/wf.cwl",
            wf_attachment=[],
            wf_attachment_obj=None,
        )
    assert exc_info.value.status_code == 400


# === validate_wf_type_and_version: edge cases ===


def test_validate_wf_type_and_version_with_empty_version_list_and_none_raises_400(mocker: "MockerFixture") -> None:
    si = _make_service_info(
        wf_type_versions={
            "CWL": WorkflowTypeVersion(workflow_type_version=[]),
        },
    )
    mocker.patch("sapporo.validator.create_service_info", return_value=si)

    with pytest.raises(HTTPException) as exc_info:
        validate_wf_type_and_version("CWL", None)
    assert exc_info.value.status_code == 400


def test_validate_wf_type_and_version_with_none_version_list_and_none_raises_400(mocker: "MockerFixture") -> None:
    si = _make_service_info(
        wf_type_versions={
            "CWL": WorkflowTypeVersion(workflow_type_version=None),
        },
    )
    mocker.patch("sapporo.validator.create_service_info", return_value=si)

    with pytest.raises(HTTPException) as exc_info:
        validate_wf_type_and_version("CWL", None)
    assert exc_info.value.status_code == 400


def test_validate_wf_type_and_version_with_explicit_version_returns_it(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())

    wf_type, wf_version = validate_wf_type_and_version("CWL", "v1.1")

    assert wf_type == "CWL"
    assert wf_version == "v1.1"
    assert isinstance(wf_type, str)
    assert isinstance(wf_version, str)


# === validate_wf_engine_type_and_version: edge cases ===


def test_validate_wf_engine_type_and_version_with_empty_version_list_returns_none(
    mocker: "MockerFixture",
) -> None:
    si = _make_service_info(
        wf_engine_versions={
            "cwltool": WorkflowEngineVersion(workflow_engine_version=[]),
        },
    )
    mocker.patch("sapporo.validator.create_service_info", return_value=si)

    engine, version = validate_wf_engine_type_and_version("cwltool", None)

    assert engine == "cwltool"
    assert version is None


def test_validate_wf_engine_type_and_version_with_none_version_list_returns_none(
    mocker: "MockerFixture",
) -> None:
    si = _make_service_info(
        wf_engine_versions={
            "cwltool": WorkflowEngineVersion(workflow_engine_version=None),
        },
    )
    mocker.patch("sapporo.validator.create_service_info", return_value=si)

    engine, version = validate_wf_engine_type_and_version("cwltool", None)

    assert engine == "cwltool"
    assert version is None


def test_validate_wf_engine_type_and_version_with_explicit_version_returns_it(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.validator.create_service_info", return_value=_make_service_info())

    engine, version = validate_wf_engine_type_and_version("nextflow", "22.04")

    assert engine == "nextflow"
    assert version == "22.04"
    assert isinstance(engine, str)
    assert isinstance(version, str)


# === validate_run_id: additional edge cases ===


def test_validate_run_id_with_matching_username_succeeds(mocker: "MockerFixture", tmp_path: Path) -> None:
    from sapporo.config import AppConfig

    app_config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, app_config)

    run_id = "abcd1234-5678-9012-3456-789012345678"
    run_dir = tmp_path.joinpath(run_id[:2]).joinpath(run_id)
    run_dir.mkdir(parents=True)

    username_file = run_dir.joinpath("username.txt")
    username_file.write_text("alice", encoding="utf-8")

    validate_run_id(run_id, "alice")  # Should not raise


def test_validate_run_id_uses_first_two_chars_as_directory_prefix(mocker: "MockerFixture", tmp_path: Path) -> None:
    from sapporo.config import AppConfig

    app_config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, app_config)

    run_id = "ff001234-5678-9012-3456-789012345678"
    expected_dir = tmp_path / "ff" / run_id
    expected_dir.mkdir(parents=True)

    validate_run_id(run_id, None)  # Should find via run_id[:2] prefix

    # Verify a different prefix does not exist
    wrong_dir = tmp_path / "ab" / run_id
    assert not wrong_dir.exists()
