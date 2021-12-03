#!/usr/bin/env python3
# coding: utf-8
from sys import version_info
from typing import Any, Dict, List, Literal, Optional, Union

if version_info.minor < 8:
    from typing_extensions import TypedDict
else:
    from typing import TypedDict


class DefaultWorkflowEngineParameter(TypedDict):
    name: str
    type: str
    default_value: str


class Log(TypedDict):
    name: str
    cmd: List[str]
    start_time: Optional[str]
    end_time: Optional[str]
    stdout: Optional[str]
    stderr: Optional[str]
    exit_code: Optional[int]


class WorkflowTypeVersion(TypedDict):
    workflow_type_version: List[str]


class ServiceInfo(TypedDict):
    workflow_type_versions: Dict[str, WorkflowTypeVersion]
    supported_wes_versions: List[str]
    default_wes_version: str
    default_wes_parameters: List[DefaultWorkflowEngineParameter]
    supported_filesystem_protocols: List[str]
    workflow_engine_versions: List[str]
    default_workflow_engine_parameters: Union[List[DefaultWorkflowEngineParameter],
                                              Dict[str, List[DefaultWorkflowEngineParameter]]]
    system_state_count: Dict[str, int]
    auth_instructions_url: str
    contact_info_url: str
    tags: Dict[str, str]


class SecondaryFile(TypedDict):
    required: bool
    pattern: str


class WorkflowInput(TypedDict):
    default: Optional[Union[str, int, bool]]
    doc: Optional[str]
    id: str
    label: Optional[str]
    type: Literal["file", "directory", "any", "string", "integer", "boolean"]
    array: bool
    required: bool
    secondary_files: Optional[List[SecondaryFile]]


class ParseResult(TypedDict):
    workflow_type: str
    workflow_type_version: str
    inputs: List[WorkflowInput]


State = Literal[
    "UNKNOWN",
    "QUEUED",
    "INITIALIZING",
    "RUNNING",
    "PAUSED",
    "COMPLETE",
    "EXECUTOR_ERROR",
    "SYSTEM_ERROR",
    "CANCELED",
    "CANCELING"
]


class RunStatus(TypedDict):
    run_id: str
    state: State


class RunListResponse(TypedDict):
    runs: List[RunStatus]
    next_page_token: str


class AttachedFile(TypedDict):
    file_name: str
    file_url: str


class RunRequest(TypedDict):
    workflow_parames: Union[Dict[str, Any], str]
    workflow_type: Optional[str]
    workflow_type_version: Optional[str]
    tags: Optional[Dict[str, str]]
    workflow_engine_name: str
    workflow_engine_parameters: Union[Dict[str, Any], List[str]]
    workflow_url: Optional[str]
    workflow_name: Optional[str]
    workflow_attachment: Optional[Union[List[str], List[AttachedFile]]]


class RunLog(TypedDict):
    run_id: str
    request: RunRequest
    state: State
    run_log: Log
    task_logs: List[Log]
    outputs: List[AttachedFile]


class RunId(TypedDict):
    run_id: str


class ErrorResponse(TypedDict):
    msg: str
    status_code: int


class Workflow(TypedDict):
    workflow_name: str
    workflow_url: str
    workflow_type: str
    workflow_type_version: str
    workflow_attachment: List[AttachedFile]
