#!/usr/bin/env python3
# coding: utf-8
from enum import Enum, auto
from sys import version_info
from typing import Any, Dict, List

if version_info.minor < 8:
    from typing_extensions import TypedDict
else:
    from typing import TypedDict  # type: ignore


class DefaultWorkflowEngineParameter(TypedDict):
    """
    Each workflow engine can present additional parameters that can be sent to
    the workflow engine. This message will list the default values, and their
    types for each workflow engine.

    name:
        The name of the parameter
    type:
        Describes the type of the parameter, e.g. float.
    default_value:
        The stringified version of the default parameter. e.g. "2.45".
    """
    name: str
    type: str
    default_value: str


class Log(TypedDict):
    """
    Log and other info

    name:
        The task or workflow name
    cmd:
        The command line that was executed
    start_time:
        When the command started executing, in ISO 8601 format
        "%Y-%m-%dT%H:%M:%SZ"
    end_time:
        When the command stopped executing (completed, failed, or cancelled),
        in ISO 8601 format "%Y-%m-%dT%H:%M:%SZ"
    stdout:
        A URL to retrieve standard output logs of the workflow run or task.
        This URL may change between status requests, or may not be available
        until the task or workflow has finished execution. Should be available
        using the same credentials used to access the WES endpoint.
    stderr:
        A URL to retrieve standard error logs of the workflow run or task.
        This URL may change between status requests, or may not be available
        until the task or workflow has finished execution. Should be available
        using the same credentials used to access the WES endpoint.
    exit_code:
        Exit code of the program
    """
    name: str
    cmd: List[str]
    start_time: str
    end_time: str
    stdout: str
    stderr: str
    exit_code: int


class State(Enum):
    """
    UNKNOWN:
        The state of the task is unknown. This provides a safe default for
        messages where this field is missing, for example, so that a missing
        field does not accidentally imply that the state is QUEUED.
    QUEUED:
        The task is queued.
    INITIALIZING:
        The task has been assigned to a worker and is currently preparing to
        run. For example, the worker may be turning on, downloading input
        files, etc.
    RUNNING:
        The task is running. Input files are downloaded and the first Executor
        has been started.
    PAUSED:
        The task is paused. An implementation may have the ability to pause a
        task, but this is not required.
    COMPLETE:
        The task has completed running. Executors have exited without error
        and output files have been successfully uploaded.
    EXECUTOR_ERROR:
        The task encountered an error in one of the Executor processes.
        Generally, this means that an Executor exited with a non-zero exit
        code.
    SYSTEM_ERROR:
        The task was stopped due to a system error, but not from an Executor,
        for example an upload failed due to network issues, the worker's ran
        out of disk space, etc.
    CANCELED:
        The task was canceled by the user.
    CANCELING:
        The task was canceled by the user, and is in the process of stopping.
    """
    UNKNOWN = auto()
    QUEUED = auto()
    INITIALIZING = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETE = auto()
    EXECUTOR_ERROR = auto()
    SYSTEM_ERROR = auto()
    CANCELED = auto()
    CANCELING = auto()


class WorkflowTypeVersion(TypedDict):
    """
    Available workflow types supported by a given instance of the service.

    workflow_type_version:
        an array of one or more acceptable types for the `workflow_type`
    """
    workflow_type_version: List[str]


class AttachedFile(TypedDict):
    """
    The file specified in `workflow_attachment`. It is expanded to the
    execution dir when the workflow is executed.

    file_name:
        File name. It can be also specified like `dir_name/file_name`.
    file_url:
        Remote file URL.
    """
    file_name: str
    file_url: str


class Workflow(TypedDict):
    """
    The information about the workflow provided by `service-info` in the mode
    of executing only the workflow registered by the administrator.

    workflow_name:
        The workflow name
    workflow_url:
        The workflow document url
    workflow_type:
        The workflow descriptor type, must be "CWL" or "WDL" currently (or
        another alternative supported by this WES instance)
    workflow_type_version:
        A map with keys as the workflow format type name (currently only CWL
        and WDL are used although a service may support others) and value is a
        workflow_type_version object which simply contains an array of one or
        more version strings
    workflow_attachment:
        The workflow_attachment array may be used to download files that are
        required to execute the workflow, including the primary workflow,
        tools imported by the workflow, other files referenced by the workflow,
        or files which are part of the input. The implementation should stage
        these files to a temporary directory and execute the workflow from
        there.
    """
    workflow_name: str
    workflow_url: str
    workflow_type: str
    workflow_type_version: str
    workflow_attachment: List[AttachedFile]


class ServiceInfo(TypedDict):
    """
    A message containing useful information about the running service,
    including supported versions and default settings.

    workflow_type_versions:
        A map with keys as the workflow format type name (currently only CWL
        and WDL are used although a service may support others) and value is a
        workflow_type_version object which simply contains an array of one or
        more version strings
    supported_wes_versions:
        The version(s) of the WES schema supported by this service
    supported_filesystem_protocols:
        The filesystem protocols supported by this service, currently these may
        include common protocols using the terms 'http', 'https', 'sftp', 's3',
        'gs', 'file', or 'synapse', but others are possible and the terms
        beyond these core protocols are currently not fixed. This section
        reports those protocols (either common or not) supported by this WES
        service.
    workflow_engine_versions:
        The engine(s) used by this WES service, key is engine name
        (e.g. Cromwell) and value is version
    default_workflow_engine_parameters:
        Each workflow engine can present additional parameters that can be
        sent to the workflow engine. This message will list the default values,
        and their types for each workflow engine.
    system_state_counts:
        The system statistics, key is the statistic, value is the count of
        runs in that state. See the State enum for the possible keys.
    auth_instructions_url:
        A web page URL with human-readable instructions on how to get an
        authorization token for use with a specific WES endpoint.
    contact_info_url:
        An email address URL (mailto:) or web page URL with contact
        information for the operator of a specific WES endpoint. Users of the
        endpoint should use this to report problems or security
        vulnerabilities.
    tags:
        A key-value map of arbitrary, extended metadata outside the scope of
        the above but useful to report back
    executable_workflows:
        List of workflows that can be executed
    """
    workflow_type_versions: Dict[str, WorkflowTypeVersion]
    supported_wes_versions: List[str]
    supported_filesystem_protocols: List[str]
    workflow_engine_versions: Dict[str, str]
    default_workflow_engine_parameters: List[DefaultWorkflowEngineParameter]
    system_state_counts: Dict[State, int]
    auth_instructions_url: str
    contact_info_url: str
    tags: Dict[str, str]
    executable_workflows: List[Workflow]


class RunStatus(TypedDict):
    """
    Small description of a workflow run, returned by server during listing
    """
    run_id: str
    state: State


class RunListResponse(TypedDict):
    """
    The service will return a RunListResponse when receiving a successful
    RunListRequest.

    runs:
        A list of workflow runs that the service has executed or is executing.
        The list is filtered to only include runs that the caller has
        permission to see.
    next_page_token:
        A token which may be supplied as `page_token` in workflow run list
        request to get the next page of results. An empty string indicates
        there are no more items to return.
    """
    runs: List[RunStatus]
    next_page_token: str


class RunRequest(TypedDict):
    """
    To execute a workflow, send a run request including all the details needed
    to begin downloading and executing a given workflow.

    workflow_params:
        The workflow run parameterizations (JSON encoded), including input and
        output file locations
    workflow_type:
        The workflow descriptor type, must be "CWL" or "WDL" currently (or
        another alternative supported by this WES instance)
    workflow_type_version:
        The workflow descriptor type version, must be one supported by this
        WES instance
    tags:
        A key-value map of arbitrary metadata outside the scope of
        `workflow_params` but useful to track with this run request
    workflow_engine_name:
        Specify the name of the workflow engine to run workflow.
    workflow_engine_parameters:
        Additional parameters can be sent to the workflow engine using this
        field. Default values for these parameters can be obtained using the
        ServiceInfo endpoint.
    workflow_url:
        The workflow CWL or WDL document. When `workflow_attachments` is used
        to attach files, the `workflow_url` may be a relative path to one of
        the attachments.
    workflow_name:
        The `workflow_name` is only used when SAPPORO is in the mode to
        execute only registered workflows. In the original EWS, it is
        OPTIONAL. To see the registered workflows, use `GET /service-info`.
    workflow_attachment:
        The workflow_attachment array may be used to upload files that are
        required to execute the workflow, including the primary workflow,
        tools imported by the workflow, other files referenced by the workflow,
        or files which are part of the input. The implementation should stage
        these files to a temporary directory and execute the workflow from
        there. These parts must have a Content-Disposition header with a
        "filename" provided for each part. Filenames may include
        subdirectories, but must not include references to parent directories
        with '..' -- implementations should guard against maliciously
        constructed filenames.
    """
    workflow_params: str
    workflow_type: str
    workflow_type_version: str
    tags: str
    workflow_engine_name: str
    workflow_engine_parameters: str
    workflow_url: str
    workflow_name: str
    workflow_attachment: List[AttachedFile]


class RunLog(TypedDict):
    """
    run_id:
      workflow run ID
    request:
      The original request message used to initiate this execution.
    state:
      The state of the run e.g. RUNNING (see State)
    run_log:
      The logs, and other key info like timing and exit code, for the overall
      run of this workflow.
    task_logs:
      The logs, and other key info like timing and exit code, for each step in
      the workflow run.
    outputs:
      The outputs from the workflow run.
    """
    run_id: str
    request: RunRequest
    state: State
    run_log: Log
    task_logs: List[Log]
    outputs: Dict[Any, Any]


class RunId(TypedDict):
    """
    workflow run ID
    """
    run_id: str


class ErrorResponse(TypedDict):
    """
    An object that can optionally include information about the error.

    msg:
        A detailed error message.
    status_code:
        The integer representing the HTTP status code (e.g. 200, 404).
    """
    msg: str
    status_code: int
