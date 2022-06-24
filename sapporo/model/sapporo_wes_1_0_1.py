#!/usr/bin/env python3
# coding: utf-8
from typing import Dict, List, Literal, Optional, TypedDict, Union

WorkflowTypes = Optional[Literal["CWL", "WDL", "SMK", "NFL"]]


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


class ServiceInfo(TypedDict):
    workflow_type_versions: Dict[WorkflowTypes, WorkflowTypeVersion]
    supported_wes_versions: List[str]
    supported_filesystem_protocols: List[str]
    workflow_engine_versions: Dict[str, str]
    default_workflow_engine_parameters: Dict[str,
                                             List[DefaultWorkflowEngineParameter]]
    system_state_counts: Dict[State, int]
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


class ParseRequest(TypedDict):
    workflow_content: Optional[str]
    workflow_location: Optional[str]
    types_of_parsing: Optional[List[str]]


class ParseResult(TypedDict):
    workflow_type: Optional[WorkflowTypes]
    workflow_type_version: Optional[str]
    inputs: Optional[Union[List[WorkflowInput], str]]


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
    workflow_params: Optional[str]
    workflow_type: Optional[WorkflowTypes]
    workflow_type_version: Optional[str]
    tags: Optional[str]
    workflow_engine_name: str
    workflow_engine_parameters: Optional[str]
    workflow_url: Optional[str]
    workflow_name: Optional[str]
    workflow_attachment: Optional[str]


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
