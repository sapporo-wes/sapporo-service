import json
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pydantic import TypeAdapter

from sapporo.config import get_config
from sapporo.schemas import (DefaultWorkflowEngineParameter,
                             ExecutableWorkflows, FileObject, Log,
                             Organization, OutputsListResponse, RunLog,
                             RunRequest, RunStatus, RunSummary, ServiceInfo,
                             ServiceType, WorkflowEngineVersion,
                             WorkflowTypeVersion)
from sapporo.utils import now_str, sapporo_version


@lru_cache(maxsize=None)
def create_service_info() -> ServiceInfo:
    """\
    Create ServiceInfo object from service_info file and default values.

    Do not validate the service_info file.
    Because if the field does not exist, the default value is used, and the field value is validated when the ServiceInfo is instantiated.

    To enable caching, `system_state_counts` is set to an empty dict.
    """
    app_config = get_config()
    service_info_path = app_config.service_info
    with service_info_path.open(mode="r", encoding="utf-8") as f:
        file_obj: Dict[str, Any] = json.load(f)

    wf_type_versions = TypeAdapter(Dict[str, WorkflowTypeVersion]).validate_python(file_obj.get("workflow_type_versions", {}))
    wf_engine_versions = TypeAdapter(Dict[str, WorkflowEngineVersion]).validate_python(file_obj.get("workflow_engine_versions", {}))
    default_wf_engine_params = TypeAdapter(Dict[str, List[DefaultWorkflowEngineParameter]]).\
        validate_python(file_obj.get("default_workflow_engine_parameters", {}))

    now = now_str()

    return ServiceInfo(
        id=file_obj.get("id", "sapporo-service"),
        name=file_obj.get("name", "sapporo-service"),
        type=ServiceType(
            group=file_obj.get("type", {}).get("group", "sapporo-wes"),
            artifact=file_obj.get("type", {}).get("artifact", "wes"),
            version=file_obj.get("type", {}).get("version", "sapporo-wes-2.0.0"),
        ),
        description=file_obj.get("description", "The instance of the Sapporo-WES."),
        organization=Organization(
            name=file_obj.get("organization", {}).get("name", "Sapporo-WES Project Team"),
            url=file_obj.get("organization", {}).get("url", "https://github.com/orgs/sapporo-wes/people"),
        ),
        contactUrl=file_obj.get("contactUrl", "https://github.com/sapporo-wes/sapporo-service/issues"),
        documentationUrl=file_obj.get("documentationUrl", "https://github.com/sapporo-wes/sapporo-service/blob/main/README.md"),
        createdAt=file_obj.get("createdAt", now),
        updatedAt=file_obj.get("updatedAt", now),
        version=file_obj.get("version", sapporo_version()),
        environment=file_obj.get("environment", None),
        workflow_type_versions=wf_type_versions,
        supported_wes_versions=file_obj.get("supported_wes_versions", ["1.1.0", "sapporo-wes-2.0.0"]),
        supported_filesystem_protocols=file_obj.get("supported_filesystem_protocols", ["http", "https", "file"]),
        workflow_engine_versions=wf_engine_versions,
        default_workflow_engine_parameters=default_wf_engine_params,
        system_state_counts={},  # Empty dict to enable caching
        auth_instructions_url=file_obj.get("auth_instructions_url", "https://github.com/sapporo-wes/sapporo-service/blob/main/README.md#authentication"),
        tags=file_obj.get("tags", {}),
    )


def create_run_log(run_id: str) -> RunLog:
    # Avoid circular import
    from sapporo.run import read_file, read_state  # pylint: disable=C0415

    # Use local var. for type hint
    request: Optional[RunRequest] = read_file(run_id, "run_request")
    outputs: Optional[List[FileObject]] = read_file(run_id, "outputs")

    return RunLog(
        run_id=run_id,
        request=request,
        state=read_state(run_id),
        run_log=create_log(run_id),
        task_logs_url=None,  # not used
        task_logs=None,  # not used
        outputs=outputs,
    )


def create_log(run_id: str) -> Log:
    # Avoid circular import
    from sapporo.run import read_file  # pylint: disable=C0415

    # Use local var. for type hint
    cmd: Optional[List[str]] = read_file(run_id, "cmd")
    start_time: Optional[str] = read_file(run_id, "start_time")
    end_time: Optional[str] = read_file(run_id, "end_time")
    stdout: Optional[str] = read_file(run_id, "stdout")
    stderr: Optional[str] = read_file(run_id, "stderr")
    exit_code: Optional[int] = read_file(run_id, "exit_code")
    system_logs: Optional[List[str]] = read_file(run_id, "system_logs")

    return Log(
        name=None,  # not used
        cmd=cmd,
        start_time=start_time,
        end_time=end_time,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        system_logs=system_logs,
    )


def create_run_status(run_id: str) -> RunStatus:
    # Avoid circular import
    from sapporo.run import read_state  # pylint: disable=C0415

    return RunStatus(
        run_id=run_id,
        state=read_state(run_id)
    )


def create_run_summary(run_id: str) -> RunSummary:
    # Avoid circular import
    from sapporo.run import read_file, read_state  # pylint: disable=C0415

    # Use local var. for type hint
    start_time: Optional[str] = read_file(run_id, "start_time")
    end_time: Optional[str] = read_file(run_id, "end_time")
    run_request: Optional[RunRequest] = read_file(run_id, "run_request")
    if run_request is None:
        tags: Dict[str, str] = {}
    else:
        if run_request.tags is None:
            tags = {}
        else:
            tags = run_request.tags

    return RunSummary(
        run_id=run_id,
        state=read_state(run_id),
        start_time=start_time,
        end_time=end_time,
        tags=tags,
    )


def create_outputs_list_response(run_id: str) -> OutputsListResponse:
    # Avoid circular import
    from sapporo.run import read_file  # pylint: disable=C0415

    # Use local var. for type hint
    outputs: Optional[List[FileObject]] = read_file(run_id, "outputs")

    return OutputsListResponse(
        outputs=outputs or [],
    )


@lru_cache(maxsize=None)
def create_executable_wfs() -> ExecutableWorkflows:
    executable_wfs_path = get_config().executable_workflows
    if executable_wfs_path.exists():
        with executable_wfs_path.open(mode="r", encoding="utf-8") as f:
            return ExecutableWorkflows.model_validate_json(f.read())
    else:
        return ExecutableWorkflows(workflows=[])


def create_ro_crate_response(run_id: str) -> Dict[str, Any]:
    # Avoid circular import
    from sapporo.run import read_file  # pylint: disable=C0415

    ro_crate: Dict[str, Any] = read_file(run_id, "ro_crate")

    return ro_crate
