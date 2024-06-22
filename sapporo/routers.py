from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, Query, UploadFile

from sapporo.config import GA4GH_WES_SPEC, LOGGER
from sapporo.factory import create_service_info
from sapporo.schemas import (RunId, RunListResponse, RunLog, RunStatus,
                             ServiceInfo, TaskListResponse, TaskLog)
from sapporo.validator import validate_run_request

router = APIRouter()


@router.get(
    "/service-info",
    summary=GA4GH_WES_SPEC["paths"]["/service-info"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/service-info"]["get"]["description"],
    response_model=ServiceInfo
)
async def get_service_info() -> ServiceInfo:
    service_info = create_service_info()
    # TODO update system_state_count
    return service_info


@router.get(
    "/runs",
    summary=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["description"],
)
async def list_runs(
    page_size: Optional[int] = Query(
        None,
        description=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["parameters"][0]["description"],
    ),
    page_token: Optional[str] = Query(
        None,
        description=GA4GH_WES_SPEC["paths"]["/runs"]["get"]["parameters"][1]["description"],
    )
) -> RunListResponse:
    raise NotImplementedError("Not implemented")


@router.post(
    "/runs",
    summary=GA4GH_WES_SPEC["paths"]["/runs"]["post"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs"]["post"]["description"],
)
async def run_workflow(
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
    return RunId(run_id=run_id)


@router.get(
    "/runs/{run_id}",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}"]["get"]["description"],
)
async def get_run_log(
    run_id: str
) -> RunLog:
    raise NotImplementedError("Not implemented")


@router.get(
    "/runs/{run_id}/status",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/status"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/status"]["get"]["description"],
)
async def get_run_status(
    run_id: str
) -> RunStatus:
    raise NotImplementedError("Not implemented")


@router.get(
    "/runs/{run_id}/tasks",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks"]["get"]["description"],
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
    raise NotImplementedError("Not implemented")


@router.get(
    "/runs/{run_id}/tasks/{task_id}",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks/{task_id}"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/tasks/{task_id}"]["get"]["description"],
)
async def get_task(
    run_id: str,
    task_id: str
) -> TaskLog:
    raise NotImplementedError("Not implemented")


@router.post(
    "/runs/{run_id}/cancel",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/cancel"]["post"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}/cancel"]["post"]["description"],
)
async def cancel_run(
    run_id: str
) -> RunId:
    raise NotImplementedError("Not implemented")
