from typing import Literal, cast
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from sapporo.auth import (
    MeResponse,
    TokenResponse,
    auth_depends_factory,
    create_access_token,
    decode_token,
    extract_username,
    is_create_token_endpoint_enabled,
)
from sapporo.config import GA4GH_WES_SPEC, SAPPORO_WES_SPEC_VERSION
from sapporo.database import add_run_db, count_runs_db, db_runs_to_run_summaries, list_runs_db, system_state_counts
from sapporo.exceptions import raise_bad_request, raise_not_found
from sapporo.factory import (
    create_executable_wfs,
    create_outputs_list_response,
    create_ro_crate_response,
    create_run_log,
    create_run_status,
    create_run_summary,
    create_service_info,
)
from sapporo.run import (
    bulk_delete_run_tasks,
    cancel_run_task,
    delete_run_task,
    outputs_zip_stream,
    post_run_task,
    prepare_run_dir,
    resolve_content_path,
    ro_crate_zip_stream,
)
from sapporo.schemas import (
    BulkDeleteResponse,
    ExecutableWorkflows,
    OutputsListResponse,
    RunId,
    RunListResponse,
    RunLog,
    RunRequestJson,
    RunStatus,
    ServiceInfo,
    State,
    TaskListResponse,
    TaskLog,
)
from sapporo.utils import secure_filepath
from sapporo.validator import validate_run_id, validate_run_request

router = APIRouter()

_EXT = f"**sapporo-wes-{SAPPORO_WES_SPEC_VERSION} extension:**"


@router.get(
    "/service-info",
    summary=GA4GH_WES_SPEC["paths"]["/service-info"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/service-info"]["get"]["description"]
    + f"""\n
{_EXT}

- `system_state_count` is a snapshot that is aggregated every 30 minutes. It may not represent the latest state.
- When authentication is enabled and a valid token is provided, `system_state_counts` shows only the runs belonging to the authenticated user.
""",
    response_model=ServiceInfo,
)
async def get_service_info(
    token: str | None = auth_depends_factory(),
) -> ServiceInfo:
    service_info = create_service_info()
    username = token and extract_username(decode_token(token))
    service_info.system_state_counts = system_state_counts(username)
    return service_info


@router.get(
    "/runs",
    summary=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["description"]
    + f"""\n
{_EXT}

- By default, this endpoint returns the latest state of runs (reads each run directory).
- If you want to use the snapshot for faster response, use `latest=false` query parameter. The snapshot is aggregated periodically and may not represent the latest state.
""",
    response_model=RunListResponse,
)
async def list_runs(
    page_size: int = Query(
        10,
        description=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["parameters"][0]["description"],
    ),
    page_token: str | None = Query(
        None,
        description=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["parameters"][1]["description"],
    ),
    sort_order: Literal["asc", "desc"] = Query(
        "desc",
        description=f"{_EXT} Sort order of the runs based on start_time.",
    ),
    state: State | None = Query(
        None,
        description=f'{_EXT} Filter the runs based on the state (e.g., "COMPLETE", "RUNNING", etc.).',
    ),
    run_ids: list[str] | None = Query(
        None,
        description=f"{_EXT} A list of run IDs to retrieve specific runs.",
    ),
    latest: bool | None = Query(
        True,
        description=f"{_EXT} If True, return the latest state of runs instead of the snapshot.",
    ),
    tags: list[str] | None = Query(
        None,
        description=f"{_EXT} Filter by tag key:value pairs (AND logic). Each value should be in 'key:value' format.",
    ),
    token: str | None = auth_depends_factory(),
) -> RunListResponse:
    username = token and extract_username(decode_token(token))
    (db_runs, next_page_token) = list_runs_db(page_size, page_token, sort_order, state, run_ids, username, tags)
    if latest:  # noqa: SIM108
        runs = [create_run_summary(run.run_id) for run in db_runs]
    else:
        runs = db_runs_to_run_summaries(db_runs)
    total_runs = count_runs_db(state, run_ids, username, tags)
    return RunListResponse(
        runs=runs,
        next_page_token=next_page_token,
        total_runs=total_runs,
    )


@router.post(
    "/runs",
    summary=GA4GH_WES_SPEC["paths"]["/runs"]["post"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs"]["post"]["description"]
    + f"""\n
{_EXT}

- Added a field `workflow_attachment_obj`. With this field, download files from remote locations directly to the execution directory.
- `workflow_type_version` and `workflow_url` are now required.
- Supports `application/json` request body in addition to `multipart/form-data`.
""",
    response_model=RunId,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["workflow_type", "workflow_type_version", "workflow_engine", "workflow_url"],
                        "properties": {
                            "workflow_params": {
                                "type": "string",
                                "description": GA4GH_WES_SPEC["components"]["schemas"]["RunRequest"]["properties"][
                                    "workflow_params"
                                ]["description"],
                            },
                            "workflow_type": {
                                "type": "string",
                                "description": GA4GH_WES_SPEC["components"]["schemas"]["RunRequest"]["properties"][
                                    "workflow_type"
                                ]["description"]
                                + f" Optional in original WES 1.1.0, but required in sapporo-wes-{SAPPORO_WES_SPEC_VERSION}.",
                            },
                            "workflow_type_version": {
                                "type": "string",
                                "description": GA4GH_WES_SPEC["components"]["schemas"]["RunRequest"]["properties"][
                                    "workflow_type_version"
                                ]["description"]
                                + f" Optional in original WES 1.1.0, but required in sapporo-wes-{SAPPORO_WES_SPEC_VERSION}.",
                            },
                            "tags": {
                                "type": "string",
                                "description": "JSON-encoded key-value map of arbitrary metadata tags for the run.",
                            },
                            "workflow_engine": {
                                "type": "string",
                                "description": GA4GH_WES_SPEC["components"]["schemas"]["RunRequest"]["properties"][
                                    "workflow_engine"
                                ]["description"]
                                + f" Optional in original WES 1.1.0, but required in sapporo-wes-{SAPPORO_WES_SPEC_VERSION}.",
                            },
                            "workflow_engine_version": {
                                "type": "string",
                                "description": GA4GH_WES_SPEC["components"]["schemas"]["RunRequest"]["properties"][
                                    "workflow_engine_version"
                                ]["description"],
                            },
                            "workflow_engine_parameters": {
                                "type": "string",
                                "description": "JSON-encoded additional parameters for the workflow engine.",
                            },
                            "workflow_url": {
                                "type": "string",
                                "description": GA4GH_WES_SPEC["components"]["schemas"]["RunRequest"]["properties"][
                                    "workflow_url"
                                ]["description"]
                                + f" Optional in original WES 1.1.0, but required in sapporo-wes-{SAPPORO_WES_SPEC_VERSION}.",
                            },
                            "workflow_attachment": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"},
                                "description": "Files to upload to the execution directory.",
                            },
                            "workflow_attachment_obj": {
                                "type": "string",
                                "description": f'{_EXT} JSON-encoded file objects to download to the execution directory. e.g., [{{"file_name": "path/to/file", "file_url": "https://example.com/path/to/file"}}]',
                            },
                        },
                    },
                },
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/RunRequestJson"},
                },
            },
        }
    },
)
async def run_workflow(
    request: Request,
    background_tasks: BackgroundTasks,
    token: str | None = auth_depends_factory(),
) -> RunId:
    username = token and extract_username(decode_token(token))
    run_id = str(uuid4())

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        json_req = RunRequestJson(**body)
        run_request = validate_run_request(
            str(json_req.workflow_params) if json_req.workflow_params is not None else None,
            json_req.workflow_type,
            json_req.workflow_type_version,
            str(json_req.tags) if json_req.tags is not None else None,
            json_req.workflow_engine,
            json_req.workflow_engine_version,
            str(json_req.workflow_engine_parameters) if json_req.workflow_engine_parameters is not None else None,
            json_req.workflow_url,
            [],
            str([obj.model_dump() for obj in json_req.workflow_attachment_obj])
            if json_req.workflow_attachment_obj
            else None,
        )
    else:
        form = await request.form()
        run_request = validate_run_request(
            str(form.get("workflow_params")) if form.get("workflow_params") is not None else None,
            str(form.get("workflow_type", "")),
            str(form.get("workflow_type_version", "")),
            str(form.get("tags")) if form.get("tags") is not None else None,
            str(form.get("workflow_engine", "")),
            str(form.get("workflow_engine_version")) if form.get("workflow_engine_version") is not None else None,
            str(form.get("workflow_engine_parameters")) if form.get("workflow_engine_parameters") is not None else None,
            str(form.get("workflow_url", "")),
            cast("list[UploadFile]", form.getlist("workflow_attachment")),
            str(form.get("workflow_attachment_obj")) if form.get("workflow_attachment_obj") is not None else None,
        )

    prepare_run_dir(run_id, run_request, username)
    add_run_db(create_run_summary(run_id), username)
    background_tasks.add_task(post_run_task, run_id, run_request)
    return RunId(run_id=run_id)


@router.get(
    "/runs/{run_id}",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}"]["get"]["description"]
    + f"""\n
{_EXT}

- Always check the contents of the run dir and return the latest state of the run.
""",
    response_model=RunLog,
)
async def get_run_log(
    run_id: str,
    token: str | None = auth_depends_factory(),
) -> RunLog:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    return create_run_log(run_id)


@router.get(
    "/runs/{run_id}/status",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/status"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/status"]["get"]["description"]
    + f"""\n
{_EXT}

- Always check the contents of the run dir and return the latest state of the run.
""",
    response_model=RunStatus,
)
async def get_run_status(
    run_id: str,
    token: str | None = auth_depends_factory(),
) -> RunStatus:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    return create_run_status(run_id)


@router.get(
    "/runs/{run_id}/tasks",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks"]["get"]["description"]
    + f"""\n
{_EXT}

- This endpoint is not implemented and there are no plans to implement it.
""",
    response_model=TaskListResponse,
)
async def list_tasks(
    run_id: str,
    page_size: int | None = Query(
        None,
        description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks"]["get"]["parameters"][1]["description"],
    ),
    page_token: str | None = Query(
        None,
        description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks"]["get"]["parameters"][2]["description"],
    ),
) -> TaskListResponse:
    raise_bad_request("Sorry, this endpoint is not implemented and there are no plans to implement it.")


@router.get(
    "/runs/{run_id}/tasks/{task_id}",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks/{task_id}"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks/{task_id}"]["get"]["description"]
    + f"""\n
{_EXT}

- This endpoint is not implemented and there are no plans to implement it.
""",
    response_model=TaskLog,
)
async def get_task(run_id: str, task_id: str) -> TaskLog:
    raise_bad_request("Sorry, this endpoint is not implemented and there are no plans to implement it.")


@router.post(
    "/runs/{run_id}/cancel",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/cancel"]["post"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/cancel"]["post"]["description"],
    response_model=RunId,
)
async def cancel_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    token: str | None = auth_depends_factory(),
) -> RunId:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    background_tasks.add_task(cancel_run_task, run_id)
    return RunId(run_id=run_id)


# === sapporo-wes-2.0.0 extension ===


@router.delete(
    "/runs",
    summary="DeleteRuns",
    description=f"""\
{_EXT}
Delete multiple runs and their associated files in bulk.
Each run is processed the same way as `DELETE /runs/{{run_id}}`:
if a run is in progress, it will be canceled first, then its contents will be deleted.
""",
    response_model=BulkDeleteResponse,
)
async def delete_runs(
    run_ids: list[str] = Query(..., description="Run IDs to delete."),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    token: str | None = auth_depends_factory(),
) -> BulkDeleteResponse:
    username = token and extract_username(decode_token(token))
    for rid in run_ids:
        validate_run_id(rid, username)
    background_tasks.add_task(bulk_delete_run_tasks, list(run_ids))
    return BulkDeleteResponse(run_ids=run_ids)


@router.delete(
    "/runs/{run_id}",
    summary="DeleteRun",
    description=f"""\
{_EXT}
Delete the run and associated files.
If the run is in progress, it will be canceled first.
Then, the run directory contents will be deleted, but `state.txt`, `start_time.txt`, and `end_time.txt` will not be deleted.
This is because the information that the run has been deleted should be retained.
""",
    response_model=RunId,
)
async def delete_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    token: str | None = auth_depends_factory(),
) -> RunId:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    background_tasks.add_task(delete_run_task, run_id)
    return RunId(run_id=run_id)


@router.get(
    "/executable-workflows",
    summary="ListExecutableWorkflows",
    description=f"""\
{_EXT}
Return the list of workflows that can be executed in this service.
If `workflows: []`, it indicates that there are no restrictions, and any workflow can be executed.
If `workflows` contains workflow urls, only those workflows can be executed.
""",
)
def list_executable_wfs() -> ExecutableWorkflows:
    return create_executable_wfs()


@router.get(
    "/runs/{run_id}/outputs",
    summary="ListRunOutputs",
    description=f"{_EXT} List the output files of a run. When download=true, returns all outputs as a ZIP archive.",
    response_model=None,
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/OutputsListResponse"},
                    "example": {
                        "outputs": [
                            {
                                "file_name": "output.txt",
                                "file_url": "http://localhost:1122/runs/abc123/outputs/output.txt",
                            }
                        ]
                    },
                },
                "application/zip": {
                    "schema": {"type": "string", "format": "binary"},
                    "description": "ZIP archive of all outputs (when download=true)",
                },
            },
        }
    },
)
async def get_run_outputs_list(
    run_id: str,
    download: bool = Query(
        False,
        description="Download all outputs as a zip file.",
    ),
    name: str | None = Query(
        None,
        description=f"{_EXT} Custom name for the ZIP download. "
        "Sets both the download file name ({name}.zip) and the root directory inside the ZIP. "
        "Default: sapporo_{run_id}_outputs. Ignored when download=false.",
    ),
    token: str | None = auth_depends_factory(),
) -> OutputsListResponse | StreamingResponse:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    if download:
        sanitized_name = str(secure_filepath(name)) if name else f"sapporo_{run_id}_outputs"
        return StreamingResponse(
            outputs_zip_stream(run_id, sanitized_name),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={sanitized_name}.zip"},
        )
    return create_outputs_list_response(run_id)


@router.get(
    "/runs/{run_id}/outputs/{path:path}",
    summary="DownloadRunOutput",
    description=f"{_EXT} Download a specific output file from a run.",
    response_model=None,
    responses={
        200: {
            "description": "File content",
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def get_run_outputs(
    run_id: str,
    path: str,
    token: str | None = auth_depends_factory(),
) -> FileResponse:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    file_path = resolve_content_path(run_id, "outputs_dir").joinpath(secure_filepath(path))
    if not file_path.exists():
        raise_not_found("File", path)
    return FileResponse(file_path)


@router.get(
    "/runs/{run_id}/ro-crate",
    summary="DownloadRO-Crate",
    description=f"{_EXT} Get the RO-Crate metadata (ro-crate-metadata.json) of a run. When download=true, returns the entire Crate as a ZIP archive.",
    response_model=None,
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/ld+json": {
                    "schema": {"type": "object"},
                    "description": "RO-Crate metadata in JSON-LD format",
                },
                "application/zip": {
                    "schema": {"type": "string", "format": "binary"},
                    "description": "ZIP archive of the entire RO-Crate (when download=true)",
                },
            },
        }
    },
)
async def get_run_ro_crate(
    run_id: str,
    download: bool = Query(
        False,
        description="Download the entire Crate as a zip file.",
    ),
    token: str | None = auth_depends_factory(),
) -> JSONResponse | StreamingResponse:
    username = token and extract_username(decode_token(token))
    validate_run_id(run_id, username)
    if download:
        return StreamingResponse(
            ro_crate_zip_stream(run_id),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=sapporo_{run_id}_ro_crate.zip"},
        )
    return JSONResponse(
        content=create_ro_crate_response(run_id),
        media_type="application/ld+json",
    )


@router.post(
    "/token",
    summary="CreateToken",
    description=f"""\
{_EXT}

Authenticate user and create an access token.

This endpoint supports both authentication modes:

- **Sapporo IdP mode**: Authenticates against local user credentials defined in `auth_config.json`.
  Passwords are verified using Argon2 hash comparison.
- **External IdP mode (confidential client)**: Forwards credentials to the external IdP's token endpoint.

The returned JWT token should be included in subsequent requests using the `Authorization: Bearer <token>` header.

**Security notes:**
- Tokens have a configurable expiration time (default: 24 hours, max: 168 hours)
- All tokens include `iat` (issued at) and `exp` (expiration) claims
- Passwords are never logged or stored in plaintext
""",
    response_model=TokenResponse,
    responses={
        200: {
            "description": "Successful authentication",
            "content": {
                "application/json": {
                    "example": {"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "token_type": "bearer"}
                }
            },
        },
        401: {"description": "Invalid username or password"},
    },
)
async def create_token(
    username: str = Form(..., description="The username for authentication."),
    password: str = Form(..., description="The password for authentication."),
) -> TokenResponse:
    """Authenticate user and create JWT access token.

    Args:
        username: User's username
        password: User's password (verified against Argon2 hash)

    Returns:
        TokenResponse containing the JWT access token

    Raises:
        HTTPException 401: Invalid credentials
        HTTPException 400: Token creation disabled (public client mode)

    """
    is_create_token_endpoint_enabled()
    access_token = await create_access_token(username, password)
    return TokenResponse(access_token=access_token)


@router.get(
    "/me",
    summary="GetCurrentUser",
    description=f"""\
{_EXT}

Returns information about the currently authenticated user.

This endpoint is useful for:
- Verifying that a token is valid
- Retrieving the username associated with the current session
- Testing authentication configuration

The username is extracted from the JWT token's `preferred_username` claim (if present)
or falls back to the `sub` (subject) claim.
""",
    response_model=MeResponse,
    responses={
        200: {
            "description": "Authenticated user information",
            "content": {"application/json": {"example": {"username": "user1"}}},
        },
        400: {"description": "Authentication is not enabled"},
        401: {"description": "Invalid or expired token"},
    },
)
async def get_me(
    token: str | None = auth_depends_factory(),
) -> MeResponse:
    """Get the current authenticated user's information.

    Args:
        token: JWT access token (injected via auth_depends_factory)

    Returns:
        MeResponse containing the username

    Raises:
        HTTPException 400: Authentication not enabled
        HTTPException 401: Invalid or missing token

    """
    if token is None:
        raise_bad_request("Authentication is not enabled.")
    payload = decode_token(token)
    return MeResponse(username=extract_username(payload))
