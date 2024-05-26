from typing import List, Optional

from fastapi import APIRouter, Form, Query, UploadFile

from sapporo.config import GA4GH_WES_SPEC
from sapporo.schemas import (RunId, RunListResponse, RunLog, RunStatus,
                             ServiceInfo, TaskListResponse, TaskLog)

router = APIRouter()


@router.get(
    "/service-info",
    summary=GA4GH_WES_SPEC["paths"]["/service-info"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/service-info"]["get"]["description"],
    response_model=ServiceInfo
)
async def service_info() -> ServiceInfo:
    raise NotImplementedError("Not implemented")


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
    workflow_type: Optional[str] = Form(None),
    workflow_type_version: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    workflow_engine: Optional[str] = Form(None),
    workflow_engine_version: Optional[str] = Form(None),
    workflow_engine_parameters: Optional[str] = Form(None),
    workflow_url: Optional[str] = Form(None),
    workflow_attachment: Optional[List[UploadFile]] = Form(None),
) -> RunId:
    raise NotImplementedError("Not implemented")


@router.get(
    "/runs/{run_id}",
    summary=GA4GH_WES_SPEC["paths"]["/runs/{run_id}"]["get"]["summary"],
    description=GA4GH_WES_SPEC["paths"]["/runs/{run_id}"]["get"]["description"],
)
async def get_run(
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
async def get_run_tasks(
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
async def get_run_task(
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
