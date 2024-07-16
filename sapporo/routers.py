from typing import List, Literal, Optional, Union
from uuid import uuid4

from fastapi import (APIRouter, BackgroundTasks, File, Form, HTTPException,
                     Query, UploadFile, status)
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from sapporo.auth import (MeResponse, TokenResponse, auth_depends_factory,
                          create_access_token, decode_token, extract_username,
                          is_create_token_endpoint_enabled)
from sapporo.config import GA4GH_WES_SPEC
from sapporo.database import (add_run_db, db_runs_to_run_summaries,
                              list_runs_db, system_state_counts)
from sapporo.factory import (create_executable_wfs,
                             create_outputs_list_response,
                             create_ro_crate_response, create_run_log,
                             create_run_status, create_run_summary,
                             create_service_info)
from sapporo.run import (cancel_run_task, delete_run_task, outputs_zip_stream,
                         post_run_task, prepare_run_dir, resolve_content_path,
                         ro_crate_zip_stream)
from sapporo.schemas import (ExecutableWorkflows, OutputsListResponse, RunId,
                             RunListResponse, RunLog, RunStatus, ServiceInfo,
                             State, TaskListResponse, TaskLog)
from sapporo.utils import secure_filepath
from sapporo.validator import validate_run_id, validate_run_request

router = APIRouter()


@router.get(
    "/service-info",
    summary=GA4GH_WES_SPEC["paths"]["/service-info"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/service-info"]["get"]["description"] + """\n
**sapporo-wes-2.0.0 extension:**

- `system_state_count` is a snapshot that is aggregated every 30 minutes. It may not represent the latest state.
""",
    response_model=ServiceInfo,
)
async def get_service_info() -> ServiceInfo:
    service_info = create_service_info()
    service_info.system_state_counts = system_state_counts()
    return service_info


@router.get(
    "/runs",
    summary=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["description"] + """\n
**sapporo-wes-2.0.0 extension:**

- This endpoint returns a snapshot that is aggregated every 30 minutes. It may not represent the latest state.
- If you want to get the latest state of run, use `GET /runs/{run_id}` or `GET /runs/{run_id}/status` or use `latest=true` query parameter.
""",
    response_model=RunListResponse,
)
async def list_runs(
    page_size: int = Query(
        10,
        description=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["parameters"][0]["description"],
    ),
    page_token: Optional[str] = Query(
        None,
        description=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["parameters"][1]["description"],
    ),
    sort_order: Literal["asc", "desc"] = Query(
        "desc",
        description="**sapporo-wes-2.0.0 extension:** Sort order of the runs based on start_time.",
    ),
    state: Optional[State] = Query(
        None,
        description='**sapporo-wes-2.0.0 extension:**: Filter the runs based on the state (e.g., "COMPLETE", "RUNNING", etc.).',
    ),
    run_ids: Optional[List[str]] = Query(
        None,
        description='**sapporo-wes-2.0.0 extension:**: A list of run IDs to retrieve specific runs.',
    ),
    latest: Optional[bool] = Query(
        False,
        description='**sapporo-wes-2.0.0 extension:**: If True, return the latest state of runs instead of the snapshot.',
    ),
    token: Optional[str] = auth_depends_factory(),
) -> RunListResponse:
    username = token and extract_username(decode_token(token))
    (db_runs, next_page_token) = list_runs_db(page_size, page_token, sort_order, state, run_ids, username)
    if latest:
        runs = [create_run_summary(run.run_id) for run in db_runs]
    else:
        runs = db_runs_to_run_summaries(db_runs)
    return RunListResponse(
        runs=runs,
        next_page_token=next_page_token,
    )


@router.post(
    "/runs",
    summary=GA4GH_WES_SPEC["paths"]["/runs"]["post"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs"]["post"]["description"] + """\n
**sapporo-wes-2.0.0 extension:**

- Added a field `workflow_attachment_obj`. With this field, download files from remote locations directly to the execution directory.
""",
    response_model=RunId,
)
async def run_workflow(
    background_tasks: BackgroundTasks,
    workflow_params: Optional[str] = Form(None),
    workflow_type: str = Form(
        ...,
        description="Optional in original WES 1.1.0, but required in sapporo-wes-2.0.0.",
    ),
    workflow_type_version: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    workflow_engine: str = Form(
        ...,
        description="Optional in original WES 1.1.0, but required in sapporo-wes-2.0.0.",
    ),
    workflow_engine_version: Optional[str] = Form(None),
    workflow_engine_parameters: Optional[str] = Form(None),
    workflow_url: Optional[str] = Form(None),
    workflow_attachment: List[UploadFile] = File(default_factory=list),
    workflow_attachment_obj: Optional[str] = Form(
        None,
        description='Extension specific to sapporo-wes-2.0.0: e.g., [{ "file_name": "path/to/file", "file_url": "https://example.com/path/to/file" }]',
    ),
    token: Optional[str] = auth_depends_factory(),
) -> RunId:
    username = token and extract_username(decode_token(token))
    run_id = str(uuid4())
    run_request = validate_run_request(
        workflow_params,
        workflow_type,
        workflow_type_version,
        tags,
        workflow_engine,
        workflow_engine_version,
        workflow_engine_parameters,
        workflow_url,
        workflow_attachment,
        workflow_attachment_obj,
    )
    prepare_run_dir(run_id, run_request, username)
    add_run_db(create_run_summary(run_id), username)
    background_tasks.add_task(post_run_task, run_id, run_request)
    return RunId(run_id=run_id)


@router.get(
    "/runs/{run_id}",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}"]["get"]["description"] + """\n
**sapporo-wes-2.0.0 extension:**

- Always check the contents of the run dir and return the latest state of the run.
""",
    response_model=RunLog,
)
async def get_run_log(
    run_id: str,
    token: Optional[str] = auth_depends_factory(),
) -> RunLog:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    return create_run_log(run_id)


@router.get(
    "/runs/{run_id}/status",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/status"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/status"]["get"]["description"] + """\n
**sapporo-wes-2.0.0 extension:**

- Always check the contents of the run dir and return the latest state of the run.
""",
    response_model=RunStatus,
)
async def get_run_status(
    run_id: str,
    token: Optional[str] = auth_depends_factory(),
) -> RunStatus:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    return create_run_status(run_id)


@router.get(
    "/runs/{run_id}/tasks",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks"]["get"]["description"] + """\n
**sapporo-wes-2.0.0 extension:**

- This endpoint is not implemented and there are no plans to implement it.
""",
    response_model=TaskListResponse,
)
async def list_tasks(
    run_id: str,
    page_size: Optional[int] = Query(
        None,
        description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks"]["get"]["parameters"][1]["description"],
    ),
    page_token: Optional[str] = Query(
        None,
        description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks"]["get"]["parameters"][2]["description"],
    )
) -> TaskListResponse:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Sorry, this endpoint is not implemented and there are no plans to implement it.",
    )


@router.get(
    "/runs/{run_id}/tasks/{task_id}",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks/{task_id}"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks/{task_id}"]["get"]["description"] + """\n
**sapporo-wes-2.0.0 extension:**

- This endpoint is not implemented and there are no plans to implement it.
""",
    response_model=TaskLog,
)
async def get_task(
    run_id: str,
    task_id: str
) -> TaskLog:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Sorry, this endpoint is not implemented and there are no plans to implement it.",
    )


@router.post(
    "/runs/{run_id}/cancel",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/cancel"]["post"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/cancel"]["post"]["description"],
    response_model=RunId,
)
async def cancel_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    token: Optional[str] = auth_depends_factory(),
) -> RunId:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    background_tasks.add_task(cancel_run_task, run_id)
    return RunId(run_id=run_id)


# === sapporo-wes-2.0.0 extension ===


@router.delete(
    "/runs/{run_id}",
    summary="DeleteRun",
    description="""\
**sapporo-wes-2.0.0 extension:**
Delete the run and associated files.
If the run is in progress, it will be canceled first.
Then, the contents of the run_dir will be deleted, but `state.txt`, `start_time.txt`, and `end_time.txt` will not be deleted.
This is because the information that the run has been deleted should be retained.
""",
    response_model=RunId,
)
async def delete_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    token: Optional[str] = auth_depends_factory(),
) -> RunId:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    background_tasks.add_task(delete_run_task, run_id)
    return RunId(run_id=run_id)


@router.get(
    "/executable-workflows",
    summary="ListExecutableWorkflows",
    description="""\
**sapporo-wes-2.0.0 extension:**
Return the list of workflows that can be executed in this service.
If `workflows: []`, it indicates that there are no restrictions, and any workflow can be executed.
If `workflows` contains workflow urls, only those workflows can be executed.
"""
)
def list_executable_wfs() -> ExecutableWorkflows:
    return create_executable_wfs()


@router.get(
    "/runs/{run_id}/outputs",
    summary="ListRunOutputs",
    description="**sapporo-wes-2.0.0 extension:** List the files in the outputs directory. If the download option is specified, download all outputs as a zip file.",
    response_model=None,  # Union[OutputsListResponse, FileResponse],
)
async def get_run_outputs_list(
    run_id: str,
    download: bool = Query(
        False,
        description="Download all outputs as a zip file.",
    ),
    token: Optional[str] = auth_depends_factory(),
) -> Union[OutputsListResponse, StreamingResponse]:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    if download:
        return StreamingResponse(
            outputs_zip_stream(run_id),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=sapporo_{run_id}_outputs.zip"
            }
        )
    return create_outputs_list_response(run_id)


@router.get(
    "/runs/{run_id}/outputs/{path:path}",
    summary="DownloadRunOutput",
    description="**sapporo-wes-2.0.0 extension:** Download a file in the outputs directory.",
    response_model=None,  # FileResponse
)
async def get_run_outputs(
    run_id: str,
    path: str,
    token: Optional[str] = auth_depends_factory(),
) -> FileResponse:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    file_path = resolve_content_path(run_id, "outputs_dir").joinpath(secure_filepath(path))
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {path} is not found.",
        )
    return FileResponse(file_path)


@router.get(
    "/runs/{run_id}/ro-crate",
    summary="DownloadRO-Crate",
    description="**sapporo-wes-2.0.0 extension:** Download the RO-Crate (ro-crate-metadata.json) of the run. If the download option is specified, download the entire Crate as a zip file.",
    response_model=None,  # Union[JSONResponse, FileResponse],
)
async def get_run_ro_crate(
    run_id: str,
    download: bool = Query(
        False,
        description="Download the entire Crate as a zip file.",
    ),
    token: Optional[str] = auth_depends_factory(),
) -> Union[JSONResponse, StreamingResponse]:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    if download:
        return StreamingResponse(
            ro_crate_zip_stream(run_id),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=sapporo_{run_id}_ro_crate.zip"
            }
        )
    return JSONResponse(
        content=create_ro_crate_response(run_id),
        media_type="application/ld+json",
    )


@router.post(
    "/token",
    summary="CreateToken",
    description="""\
**sapporo-wes-2.0.0 extension:**
This endpoint is used when Sapporo acts as an OpenID Connect Identity Provider (IdP)
or when an external IdP is used as a "Confidential Client".
Upon successful authentication, it issues a JWT access token.
This token is necessary for accessing other endpoints, and should be included in the "Authorization: Bearer <token>" header.
""",
    response_model=TokenResponse,
)
async def create_token(
    username: str = Form(..., description="The username for authentication."),
    password: str = Form(..., description="The password for authentication."),
) -> TokenResponse:
    is_create_token_endpoint_enabled()
    access_token = await create_access_token(username, password)
    return TokenResponse(access_token=access_token)


@router.get(
    "/me",
    summary="Me",
    description="""\
**sapporo-wes-2.0.0 extension:**
This endpoint returns the username of the authenticated user.
If authentication is not enabled, an error will be returned.
""",
    response_model=MeResponse,
)
async def get_me(
    token: Optional[str] = auth_depends_factory(),
) -> MeResponse:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication is not enabled.",
        )
    payload = decode_token(token)
    return MeResponse(username=extract_username(payload))
