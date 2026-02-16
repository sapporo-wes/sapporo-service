import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from sapporo.schemas import (
    BulkDeleteResponse,
    Organization,
    RunRequest,
    RunStatus,
    ServiceInfo,
    ServiceType,
    State,
    WorkflowTypeVersion,
)

# === State enum ===


def test_state_has_13_members() -> None:
    assert len(State) == 13


def test_state_members_are_uppercase_strings() -> None:
    for state in State:
        assert state.value == state.value.upper()
        assert isinstance(state.value, str)


EXPECTED_STATES = [
    "UNKNOWN",
    "QUEUED",
    "INITIALIZING",
    "RUNNING",
    "PAUSED",
    "COMPLETE",
    "EXECUTOR_ERROR",
    "SYSTEM_ERROR",
    "CANCELED",
    "CANCELING",
    "PREEMPTED",
    "DELETED",
    "DELETING",
]


@pytest.mark.parametrize("state_name", EXPECTED_STATES)
def test_state_contains_expected_member(state_name: str) -> None:
    assert State(state_name) is not None


@given(st.sampled_from(list(State)))
def test_state_all_members_fit_in_run_status(state: State) -> None:
    run_status = RunStatus(run_id="test-id", state=state)
    assert run_status.state == state


# === RunRequest ===


def test_run_request_with_dict_workflow_params() -> None:
    req = RunRequest(
        workflow_params={"input": "value"},
        workflow_type="CWL",
        workflow_type_version="v1.0",
        workflow_engine="cwltool",
        workflow_url="https://example.com/wf.cwl",
    )
    assert req.workflow_params == {"input": "value"}


def test_run_request_with_str_workflow_params() -> None:
    req = RunRequest(
        workflow_params="raw params string",
        workflow_type="CWL",
        workflow_type_version="v1.0",
        workflow_engine="cwltool",
        workflow_url="https://example.com/wf.cwl",
    )
    assert req.workflow_params == "raw params string"


def test_run_request_optional_fields_default_to_none() -> None:
    req = RunRequest(
        workflow_params={},
        workflow_type="CWL",
        workflow_type_version="v1.0",
        workflow_engine="cwltool",
        workflow_url="https://example.com/wf.cwl",
    )
    assert req.tags is None
    assert req.workflow_engine_version is None
    assert req.workflow_engine_parameters is None


def test_run_request_without_workflow_engine_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="workflow_engine"):
        RunRequest(  # type: ignore[call-arg]
            workflow_params={},
            workflow_type="CWL",
            workflow_type_version="v1.0",
            workflow_url="https://example.com/wf.cwl",
        )


# === BulkDeleteResponse ===


def test_bulk_delete_response_serializes_run_ids() -> None:
    resp = BulkDeleteResponse(run_ids=["id-1", "id-2", "id-3"])
    data = resp.model_dump()
    assert data == {"run_ids": ["id-1", "id-2", "id-3"]}


def test_bulk_delete_response_empty_list() -> None:
    resp = BulkDeleteResponse(run_ids=[])
    assert resp.run_ids == []


def test_bulk_delete_response_without_run_ids_raises_validation_error() -> None:
    with pytest.raises(ValidationError, match="run_ids"):
        BulkDeleteResponse()  # type: ignore[call-arg]


# === ServiceInfo ===


def test_service_info_workflow_type_versions_structure() -> None:
    service_info = ServiceInfo(
        id="test",
        name="test",
        type=ServiceType(group="org.ga4gh", artifact="wes", version="1.1.0"),
        organization=Organization(name="Test Org", url="https://example.com"),
        version="1.0.0",
        workflow_type_versions={"CWL": WorkflowTypeVersion(workflow_type_version=["v1.0", "v1.1"])},
        supported_wes_versions=["1.1.0"],
        supported_filesystem_protocols=["http", "https"],
        workflow_engine_versions={},
        default_workflow_engine_parameters={},
        system_state_counts={},
        auth_instructions_url="https://example.com/auth",
        tags={},
    )
    assert "CWL" in service_info.workflow_type_versions
    assert service_info.workflow_type_versions["CWL"].workflow_type_version == ["v1.0", "v1.1"]


# === Organization ===


def test_organization_with_valid_url_succeeds() -> None:
    org = Organization(name="Test", url="https://example.com")
    assert org.name == "Test"


def test_organization_with_invalid_url_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        Organization(name="Test", url="not-a-url")
