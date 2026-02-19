import json
import re

from fastapi import UploadFile

from sapporo.config import get_config
from sapporo.exceptions import raise_bad_request, raise_forbidden, raise_not_found
from sapporo.factory import create_executable_wfs, create_service_info
from sapporo.run_io import read_file
from sapporo.schemas import RunRequestForm

_UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_SHELL_DANGEROUS_RE = re.compile(r"[;|&$`(){}\!\n\r\x00]")


def validate_wf_engine_param_token(value: str) -> None:
    """Reject workflow engine parameter tokens containing shell-dangerous characters."""
    if _SHELL_DANGEROUS_RE.search(value):
        raise_bad_request(f"workflow_engine_parameters contains forbidden characters: {value!r}")


def validate_run_request(
    wf_params: str | None,
    wf_type: str,
    wf_type_version: str | None,
    tags: str | None,
    wf_engine: str,
    wf_engine_version: str | None,
    wf_engine_parameters: str | None,
    wf_url: str | None,
    wf_attachment: list[UploadFile],
    wf_attachment_obj: str | None,
) -> RunRequestForm:
    """Validate and convert the form-data request sent to POST /runs.

    The form data is validated and converted into an intermediate RunRequestForm schema,
    which is then used to create the final RunRequest schema for internal use.
    """
    try:
        _wf_params = json.loads(wf_params) if wf_params is not None else {}
    except json.JSONDecodeError:
        raise_bad_request("Invalid JSON in workflow_params.")
    wf_type, wf_type_version = validate_wf_type_and_version(wf_type, wf_type_version)
    try:
        _tags = json.loads(tags) if tags is not None else {}
    except json.JSONDecodeError:
        raise_bad_request("Invalid JSON in tags.")
    wf_engine, wf_engine_version = validate_wf_engine_type_and_version(wf_engine, wf_engine_version)
    try:
        wf_engine_parameters = json.loads(wf_engine_parameters) if wf_engine_parameters is not None else None
    except json.JSONDecodeError:
        raise_bad_request("Invalid JSON in workflow_engine_parameters.")
    if not wf_url:
        raise_bad_request("workflow_url is required.")
    try:
        _wf_attachment_obj = json.loads(wf_attachment_obj) if wf_attachment_obj is not None else []
    except json.JSONDecodeError:
        raise_bad_request("Invalid JSON in workflow_attachment_obj.")

    # Check executable_wfs
    executable_wfs = create_executable_wfs()
    if len(executable_wfs.workflows) != 0 and wf_url not in executable_wfs.workflows:
        raise_bad_request(
            f"Invalid workflow_url: {wf_url}. Sapporo is currently operating in the mode where only registered workflows can be executed. Please refer to GET /executable_workflows to see the list of executable workflows."
        )

    return RunRequestForm(
        workflow_params=_wf_params,
        workflow_type=wf_type,
        workflow_type_version=wf_type_version,
        tags=_tags,
        workflow_engine=wf_engine,
        workflow_engine_version=wf_engine_version,
        workflow_engine_parameters=wf_engine_parameters,
        workflow_url=wf_url,
        workflow_attachment=wf_attachment,
        workflow_attachment_obj=_wf_attachment_obj,
    )


def validate_wf_type_and_version(
    wf_type: str,
    wf_type_version: str | None = None,
) -> tuple[str, str]:
    """Validate the wf_type and wf_type_version.

    Both wf_type and wf_type_version are required.
    """
    service_info = create_service_info()
    wf_types = service_info.workflow_type_versions.keys()

    if wf_type not in wf_types:
        raise_bad_request(f"Invalid workflow_type: {wf_type}, please select from {wf_types}")
    if not wf_type_version:
        raise_bad_request("workflow_type_version is required.")

    return wf_type, wf_type_version


def validate_wf_engine_type_and_version(
    wf_engine: str,
    wf_engine_version: str | None = None,
) -> tuple[str, str | None]:
    """Validate the wf_engine and wf_engine_version.

    wf_engine_version is optional (not required by the spec).
    """
    service_info = create_service_info()
    wf_engines = service_info.workflow_engine_versions.keys()
    if wf_engine not in wf_engines:
        raise_bad_request(f"Invalid workflow_engine: {wf_engine}, please select from {wf_engines}")

    return wf_engine, wf_engine_version


def validate_run_id(run_id: str, username: str | None) -> None:
    """Validate that a run ID exists and the user has access to it.

    Note: This function directly checks the run directory without using the database.
    Although this approach may seem confusing, it is based on the concept that the master data is stored in the run directory.
    """
    if not _UUID_PATTERN.match(run_id):
        raise_bad_request(f"Invalid run_id format: {run_id}")
    specific_run_dir = get_config().run_dir.joinpath(run_id[:2]).joinpath(run_id)
    if not specific_run_dir.exists():
        raise_not_found("Run ID", run_id)

    if username is not None:
        run_username = read_file(run_id, "username")
        if run_username != username:
            raise_forbidden(f"Your username is not allowed to access run ID {run_id}.")
