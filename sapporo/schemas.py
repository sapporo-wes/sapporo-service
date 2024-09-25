from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer

from sapporo.config import GA4GH_WES_SPEC

# === Schema extensions specific to sapporo-wes-2.0.0


class FileObject(BaseModel):
    file_name: str = Field(
        ...,
        description="File name. It is a relative path from the certain directory. That is, if the file is ./some_dir/some_file, this field is 'some_dir/some_file'.",
    )
    file_url: str = Field(
        ...,
        description="Download URL of the file.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "**sapporo-wes-2.0.0 extension:** File object used in Workflow Attachment and Output files, etc.",
        }
    )


class OutputsListResponse(BaseModel):
    outputs: List[FileObject]

    model_config = ConfigDict(
        json_schema_extra={
            "description": "**sapporo-wes-2.0.0 extension:** Response schema for GET /runs/{run_id}/outputs.",
        }
    )


class ExecutableWorkflows(BaseModel):
    workflows: List[str] = Field(
        ...,
        description="List of executable workflows. Each workflow is a URL to the workflow file.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "**sapporo-wes-2.0.0 extension:** Schema for executable_workflows.json. List of workflows that can be executed in this service.",
        }
    )


# === Schemas from https://raw.githubusercontent.com/ga4gh-discovery/ga4gh-service-info/v1.0.0/service-info.yaml ===


class ServiceType(BaseModel):
    group: str = Field(
        ...,
        description="Namespace in reverse domain name format. Use `org.ga4gh` for implementations compliant with official GA4GH specifications. For services with custom APIs not standardized by GA4GH, or implementations diverging from official GA4GH specifications, use a different namespace (e.g. your organization's reverse domain name).",
        examples=["org.ga4gh"])
    artifact: str = Field(
        ...,
        description="Name of the API or GA4GH specification implemented. Official GA4GH types should be assigned as part of standards approval process. Custom artifacts are supported.",
        examples=["beacon"])
    version: str = Field(
        ...,
        description="Version of the API or specification. GA4GH specifications use semantic versioning.",
        examples=["1.0.0"])

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Type of a GA4GH service.",
        }
    )


class Organization(BaseModel):
    name: str = Field(
        ...,
        description="Name of the organization responsible for the service.",
        examples=["My organization"])
    url: HttpUrl = Field(
        ...,
        description="URL of the website of the organization (RFC 3986 format).",
        examples=["https://example.com"])

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Organization providing the service.",
        }
    )


class Service(BaseModel):
    id: str = Field(
        ...,
        description="Unique ID of this service. Reverse domain name notation is recommended, though not required. The identifier should attempt to be globally unique so it can be used in downstream aggregator services e.g. Service Registry.",
        examples=["org.ga4gh.myservice"])
    name: str = Field(
        ...,
        description="Name of this service. Should be human readable.",
        examples=["My project"])
    type: ServiceType = Field(
        ...,
        description="GA4GH service.")
    description: Optional[str] = Field(
        None,
        description="Description of the service. Should be human readable and provide information about the service.",
        examples=["This service provides..."])
    organization: Organization = Field(
        ...,
        description="Organization providing the service.")
    contactUrl: Optional[HttpUrl] = Field(
        None,
        description="URL of the contact for the provider of this service, e.g. a link to a contact form (RFC 3986 format), or an email (RFC 2368 format).",
        examples=["mailto:support@example.com"])
    documentationUrl: Optional[HttpUrl] = Field(
        None,
        description="URL of the documentation of this service (RFC 3986 format). This should help someone learn how to use your service, including any specifics required to access data, e.g. authentication.",
        examples=["https://docs.myservice.example.com"])
    createdAt: Optional[str] = Field(
        None,
        description="Timestamp describing when the service was first deployed and available (RFC 3339 format).",
        examples=["2019-06-04T12:58:19Z"])
    updatedAt: Optional[str] = Field(
        None,
        description="Timestamp describing when the service was last updated (RFC 3339 format).",
        examples=["2019-06-04T12:58:19Z"])
    environment: Optional[str] = Field(
        None,
        description="Environment the service is running in. Use this to distinguish between production, development and testing/staging deployments. Suggested values are prod, test, dev, staging. However this is advised and not enforced.",
        examples=["test"])
    version: str = Field(
        ...,
        description="Version of the service being described. Semantic versioning is recommended, but other identifiers, such as dates or commit hashes, are also allowed. The version should be changed whenever the service is updated.",
        examples=["1.0.0"])

    model_config = ConfigDict(
        json_schema_extra={
            "description": "GA4GH service.",
        }
    )


# === Schemas from ./ga4gh-wes-spec-1.1.0.yml ===


GA4GH_WES_SCHEMAS = GA4GH_WES_SPEC["components"]["schemas"]


class WorkflowTypeVersion(BaseModel):
    workflow_type_version: Optional[List[str]] = Field(
        [],
        description=GA4GH_WES_SCHEMAS["WorkflowTypeVersion"]["properties"]["workflow_type_version"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["WorkflowTypeVersion"]["description"],
        }
    )


class WorkflowEngineVersion(BaseModel):
    workflow_engine_version: Optional[List[str]] = Field(
        [],
        description=GA4GH_WES_SCHEMAS["WorkflowEngineVersion"]["properties"]["workflow_engine_version"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["WorkflowEngineVersion"]["description"],
        }
    )


class DefaultWorkflowEngineParameter(BaseModel):
    name: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["DefaultWorkflowEngineParameter"]["properties"]["name"]["description"],
    )
    type: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["DefaultWorkflowEngineParameter"]["properties"]["type"]["description"],
    )
    default_value: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["DefaultWorkflowEngineParameter"]["properties"]["default_value"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["DefaultWorkflowEngineParameter"]["description"],
        }
    )


class ServiceInfo(Service):
    workflow_type_versions: Dict[str, WorkflowTypeVersion] = Field(...)
    supported_wes_versions: List[str] = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ServiceInfo"]["allOf"][1]["properties"]["supported_wes_versions"]["description"],
    )
    supported_filesystem_protocols: List[str] = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ServiceInfo"]["allOf"][1]["properties"]["supported_filesystem_protocols"]["description"],
    )
    workflow_engine_versions: Dict[str, WorkflowEngineVersion] = Field(...)
    default_workflow_engine_parameters: Dict[str, List[DefaultWorkflowEngineParameter]] = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ServiceInfo"]["allOf"][1]["properties"]["default_workflow_engine_parameters"]["description"] + """\n
**sapporo-wes-2.0.0 extension:**

- original wes-1.1.0: List[DefaultWorkflowEngineParameter]
- sapporo-wes-2.0.0: Dict[str, List[DefaultWorkflowEngineParameter]]
""",
    )
    system_state_counts: Dict[str, int] = Field(...)
    auth_instructions_url: HttpUrl = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ServiceInfo"]["allOf"][1]["properties"]["auth_instructions_url"]["description"],
    )
    tags: Dict[str, str] = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ServiceInfo"]["allOf"][1]["properties"]["tags"]["additionalProperties"]["description"],
    )


class State(str, Enum):
    UNKNOWN = "UNKNOWN"
    QUEUED = "QUEUED"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"
    EXECUTOR_ERROR = "EXECUTOR_ERROR"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    CANCELED = "CANCELED"
    CANCELING = "CANCELING"
    PREEMPTED = "PREEMPTED"
    DELETED = "DELETED"  # sapporo-wes-2.0.0 extension
    DELETING = "DELETING"  # sapporo-wes-2.0.0 extension


class RunStatus(BaseModel):
    run_id: str = Field(...)
    state: Optional[State] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["State"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["RunStatus"]["description"],
        }
    )


class RunSummary(RunStatus):
    start_time: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunSummary"]["allOf"][1]["properties"]["start_time"]["description"],
    )
    end_time: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunSummary"]["allOf"][1]["properties"]["end_time"]["description"],
    )
    tags: Dict[str, str] = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["RunSummary"]["allOf"][1]["properties"]["tags"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["RunSummary"]["description"],
        }
    )


class RunListResponse(BaseModel):
    runs: Optional[List[Union[RunStatus, RunSummary]]] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunListResponse"]["properties"]["runs"]["description"],
    )
    next_page_token: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunListResponse"]["properties"]["next_page_token"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["RunListResponse"]["description"],
        }
    )


class RunRequest(BaseModel):
    workflow_params: Union[Dict[str, Any], str] = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["RunRequest"]["properties"]["workflow_params"]["description"] + """\n
**sapporo-wes-2.0.0 extension:**

- original wes-1.1.0: Dict[str, Any]
- sapporo-wes-2.0.0: Union[Dict[str, Any], str]
""",
    )
    workflow_type: str = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["RunRequest"]["properties"]["workflow_type"]["description"],
    )
    workflow_type_version: str = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["RunRequest"]["properties"]["workflow_type_version"]["description"],
    )
    tags: Optional[Dict[str, str]] = Field(None)
    workflow_engine: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunRequest"]["properties"]["workflow_engine"]["description"],
    )
    workflow_engine_version: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunRequest"]["properties"]["workflow_engine_version"]["description"],
    )
    workflow_engine_parameters: Optional[Dict[str, str]] = Field(None)
    workflow_url: str = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["RunRequest"]["properties"]["workflow_url"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["RunRequest"]["description"],
        }
    )


class RunId(BaseModel):
    run_id: str = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["RunId"]["properties"]["run_id"]["description"],
    )


class Log(BaseModel):
    name: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["name"]["description"],
    )
    cmd: Optional[List[str]] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["cmd"]["description"],
    )
    start_time: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["start_time"]["description"],
    )
    end_time: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["end_time"]["description"],
    )
    stdout: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["stdout"]["description"],
    )
    stderr: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["stderr"]["description"],
    )
    exit_code: Optional[int] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["exit_code"]["description"],
    )
    system_logs: Optional[List[str]] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["system_logs"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["Log"]["description"],
        }
    )


class TaskLog(Log):
    id: str = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["TaskLog"]["allOf"][1]["properties"]["id"]["description"],
    )
    name: str = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["name"]["description"],
    )  # Override as required
    system_logs: Optional[List[str]] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["TaskLog"]["allOf"][1]["properties"]["system_logs"]["description"],
    )
    tes_uri: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["TaskLog"]["allOf"][1]["properties"]["tes_uri"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["TaskLog"]["description"],
        }
    )


class RunLog(BaseModel):
    run_id: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunLog"]["properties"]["run_id"]["description"],
    )
    request: Optional[RunRequest] = Field(None)
    state: Optional[State] = Field(None)
    run_log: Optional[Log] = Field(None)
    task_logs_url: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunLog"]["properties"]["task_logs_url"]["description"],
    )
    task_logs: Optional[List[Union[Log, TaskLog]]] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunLog"]["properties"]["task_logs"]["description"],
    )
    outputs: Optional[List[FileObject]] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunLog"]["properties"]["outputs"]["description"] + """\n
**sapporo-wes-2.0.0 extension:**

- original wes-1.1.0: Optional[Dict[str, Any]]
- sapporo-wes-2.0.0: Optional[List[FileObject]]
""",
    )


class TaskListResponse(BaseModel):
    task_logs: Optional[List[TaskLog]] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["TaskListResponse"]["properties"]["task_logs"]["description"],
    )
    next_page_token: Optional[str] = Field(
        None,
        description=GA4GH_WES_SCHEMAS["TaskListResponse"]["properties"]["next_page_token"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["TaskListResponse"]["description"],
        }
    )


class ErrorResponse(BaseModel):
    msg: str = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ErrorResponse"]["properties"]["msg"]["description"],
    )
    status_code: int = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ErrorResponse"]["properties"]["status_code"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["ErrorResponse"]["description"],
        }
    )


# === Schemas convenient for implementation ===


class RunRequestForm(RunRequest):
    """
    Schema for internal use as an intermediate representation of form data received by POST /runs.

    The schema of the form data sent to POST /runs and the schema of RunRequest used internally in the app are slightly different.
    Therefore, the form data is first converted to this intermediate RunRequestForm schema by sapporo.validator.validate_run_request before being transformed into RunRequest.
    """
    workflow_attachment: List[UploadFile]
    workflow_attachment_obj: List[FileObject]

    @field_serializer("workflow_attachment")
    def serialize_wf_attachment(self, value: List[UploadFile]) -> List[Dict[str, Any]]:
        return [{
            "filename": file.filename,
            "size": file.size,
            "headers": dict(file.headers.items()),
            "content_type": file.content_type,
        } for file in value]
