import json
from typing import List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status

from sapporo.config import get_config
from sapporo.factory import create_executable_wfs, create_service_info
from sapporo.run import read_file
from sapporo.schemas import RunRequestForm


def validate_run_request(
    wf_params: Optional[str],
    wf_type: str,
    wf_type_version: Optional[str],
    tags: Optional[str],
    wf_engine: str,
    wf_engine_version: Optional[str],
    wf_engine_parameters: Optional[str],
    wf_url: Optional[str],
    wf_attachment: List[UploadFile],
    wf_attachment_obj: Optional[str],
) -> RunRequestForm:
    """\
    Validate and convert the form-data request sent to POST /runs.

    The form data is validated and converted into an intermediate RunRequestForm schema,
    which is then used to create the final RunRequest schema for internal use.
    """
    _wf_params = json.loads(wf_params) if wf_params is not None else {}
    wf_type, wf_type_version = validate_wf_type_and_version(wf_type, wf_type_version)
    _tags = json.loads(tags) if tags is not None else {}
    wf_engine, wf_engine_version = validate_wf_engine_type_and_version(wf_engine, wf_engine_version)
    wf_engine_parameters = json.loads(wf_engine_parameters) if wf_engine_parameters is not None else None
    wf_url = wf_url if wf_url is not None else ""
    _wf_attachment_obj = json.loads(wf_attachment_obj) if wf_attachment_obj is not None else []

    # Check executable_wfs
    executable_wfs = create_executable_wfs()
    if len(executable_wfs.workflows) != 0:
        # Need to check if the wf_url is in the executable_wfs
        if wf_url not in executable_wfs.workflows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid workflow_url: {wf_url}. Sapporo is currently operating in the mode where only registered workflows can be executed. Please refer to GET /executable_workflows to see the list of executable workflows.",
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
    wf_type_version: Optional[str] = None,
) -> Tuple[str, str]:
    """\
    Validate the wf_type and wf_type_version.
    If wf_type_version is None, get the first item from service-info.
    """
    service_info = create_service_info()
    wf_types = service_info.workflow_type_versions.keys()  # pylint: disable=E1101

    if wf_type not in wf_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid workflow_type: {wf_type}, please select from {wf_types}",
        )
    if wf_type_version is None:
        wf_type_version = service_info.workflow_type_versions[wf_type].workflow_type_version[0]  # type: ignore # pylint: disable=E1136

    return wf_type, wf_type_version


def validate_wf_engine_type_and_version(
    wf_engine: str,
    wf_engine_version: Optional[str] = None,
) -> Tuple[str, str]:
    """\
    Validate the wf_engine and wf_engine_version.
    If wf_engine_version is None, get the first item from service-info.
    """
    service_info = create_service_info()
    wf_engines = service_info.workflow_engine_versions.keys()  # pylint: disable=E1101
    if wf_engine not in wf_engines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid workflow_engine: {wf_engine}, please select from {wf_engines}",
        )
    if wf_engine_version is None:
        wf_engine_version = service_info.workflow_engine_versions[wf_engine].workflow_engine_version[0]  # type: ignore # pylint: disable=E1136

    return wf_engine, wf_engine_version


def validate_run_id(run_id: str, username: Optional[str]) -> None:
    """
    Note: This function directly checks the run directory without using the database.
    Although this approach may seem confusing, it is based on the concept that the master data is stored in the run directory.
    """
    specific_run_dir = get_config().run_dir.joinpath(run_id[:2]).joinpath(run_id)
    if not specific_run_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run ID {run_id} not found.",
        )

    if username is not None:
        run_username = read_file(run_id, "username")
        if run_username != username:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your username is not allowed to access run ID {run_id}.",
            )
