from typing import List, Literal, Optional
from uuid import uuid4

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form,
                     HTTPException, Query, UploadFile)
from sqlmodel import Session

from sapporo.config import GA4GH_WES_SPEC
from sapporo.database import add_run, db_runs_to_run_summaries, get_session
from sapporo.database import list_runs as list_runs_db
from sapporo.database import system_state_counts
from sapporo.factory import (create_run_log, create_run_status,
                             create_run_summary, create_service_info)
from sapporo.run import post_run_task, prepare_run_dir
from sapporo.schemas import (RunId, RunListResponse, RunLog, RunStatus,
                             ServiceInfo, State, TaskListResponse, TaskLog)
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
async def get_service_info(db_session: Session = Depends(get_session)) -> ServiceInfo:
    service_info = create_service_info()
    service_info.system_state_counts = system_state_counts(db_session)
    return service_info


@router.get(
    "/runs",
    summary=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["description"] + """\n
**sapporo-wes-2.0.0 extension:**

- This endpoint returns a snapshot that is aggregated every 30 minutes. It may not represent the latest state.
- If you want to get the latest state of run, use `GET /runs/{run_id}` or `GET /runs/{run_id}/status`.
""",
    response_model=RunListResponse,
)
async def list_runs(
    db_session: Session = Depends(get_session),
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
) -> RunListResponse:
    (db_runs, next_page_token) = list_runs_db(db_session, page_size, page_token, sort_order, state)
    return RunListResponse(
        runs=db_runs_to_run_summaries(db_runs),  # type: ignore
        next_page_token=next_page_token,
    )


@router.post(
    "/runs",
    summary=GA4GH_WES_SPEC["paths"]["/runs"]["post"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs"]["post"]["description"],
    response_model=RunId,
)
async def run_workflow(
    background_tasks: BackgroundTasks,
    db_session: Session = Depends(get_session),
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
) -> RunId:
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
    prepare_run_dir(run_id, run_request)
    add_run(db_session, create_run_summary(run_id))
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
    run_id: str
) -> RunLog:
    validate_run_id(run_id)
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
    run_id: str
) -> RunStatus:
    validate_run_id(run_id)
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
    raise HTTPException(status_code=400, detail="Sorry, this endpoint is not implemented and there are no plans to implement it.")


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
    raise HTTPException(status_code=400, detail="Sorry, this endpoint is not implemented and there are no plans to implement it.")


@router.post(
    "/runs/{run_id}/cancel",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/cancel"]["post"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/cancel"]["post"]["description"],
    response_model=RunId,
)
async def cancel_run(
    run_id: str
) -> RunId:
    raise NotImplementedError("Not implemented")
