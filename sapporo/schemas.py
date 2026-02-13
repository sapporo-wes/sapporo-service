from enum import Enum
from typing import Any

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
    outputs: list[FileObject]

    model_config = ConfigDict(
        json_schema_extra={
            "description": "**sapporo-wes-2.0.0 extension:** Response schema for GET /runs/{run_id}/outputs.",
        }
    )


class ExecutableWorkflows(BaseModel):
    workflows: list[str] = Field(
        ...,
        description="List of executable workflows. Each workflow is a URL to the workflow file.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "**sapporo-wes-2.0.0 extension:** Schema for executable_workflows.json. List of workflows that can be executed in this service.",
            "example": {
                "workflows": [
                    "https://raw.githubusercontent.com/common-workflow-language/common-workflow-language/main/v1.0/examples/1st-tool.cwl"
                ]
            },
        }
    )


# === Schemas from https://raw.githubusercontent.com/ga4gh-discovery/ga4gh-service-info/v1.0.0/service-info.yaml ===


class ServiceType(BaseModel):
    group: str = Field(
        ...,
        description="Namespace in reverse domain name format. Use `org.ga4gh` for implementations compliant with official GA4GH specifications. For services with custom APIs not standardized by GA4GH, or implementations diverging from official GA4GH specifications, use a different namespace (e.g. your organization's reverse domain name).",
        examples=["org.ga4gh"],
    )
    artifact: str = Field(
        ...,
        description="Name of the API or GA4GH specification implemented. Official GA4GH types should be assigned as part of standards approval process. Custom artifacts are supported.",
        examples=["beacon"],
    )
    version: str = Field(
        ...,
        description="Version of the API or specification. GA4GH specifications use semantic versioning.",
        examples=["1.0.0"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Type of a GA4GH service.",
        }
    )


class Organization(BaseModel):
    name: str = Field(
        ..., description="Name of the organization responsible for the service.", examples=["My organization"]
    )
    url: HttpUrl = Field(
        ..., description="URL of the website of the organization (RFC 3986 format).", examples=["https://example.com"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Organization providing the service.",
        }
    )


class Service(BaseModel):
    id: str = Field(
        ...,
        description="Unique ID of this service. Reverse domain name notation is recommended, though not required. The identifier should attempt to be globally unique so it can be used in downstream aggregator services e.g. Service Registry.",
        examples=["org.ga4gh.myservice"],
    )
    name: str = Field(..., description="Name of this service. Should be human readable.", examples=["My project"])
    type: ServiceType = Field(..., description="GA4GH service.")
    description: str | None = Field(
        None,
        description="Description of the service. Should be human readable and provide information about the service.",
        examples=["This service provides..."],
    )
    organization: Organization = Field(..., description="Organization providing the service.")
    contactUrl: HttpUrl | None = Field(
        None,
        description="URL of the contact for the provider of this service, e.g. a link to a contact form (RFC 3986 format), or an email (RFC 2368 format).",
        examples=["mailto:support@example.com"],
    )
    documentationUrl: HttpUrl | None = Field(
        None,
        description="URL of the documentation of this service (RFC 3986 format). This should help someone learn how to use your service, including any specifics required to access data, e.g. authentication.",
        examples=["https://docs.myservice.example.com"],
    )
    createdAt: str | None = Field(
        None,
        description="Timestamp describing when the service was first deployed and available (RFC 3339 format).",
        examples=["2019-06-04T12:58:19Z"],
    )
    updatedAt: str | None = Field(
        None,
        description="Timestamp describing when the service was last updated (RFC 3339 format).",
        examples=["2019-06-04T12:58:19Z"],
    )
    environment: str | None = Field(
        None,
        description="Environment the service is running in. Use this to distinguish between production, development and testing/staging deployments. Suggested values are prod, test, dev, staging. However this is advised and not enforced.",
        examples=["test"],
    )
    version: str = Field(
        ...,
        description="Version of the service being described. Semantic versioning is recommended, but other identifiers, such as dates or commit hashes, are also allowed. The version should be changed whenever the service is updated.",
        examples=["1.0.0"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "GA4GH service.",
        }
    )


# === Schemas from ./ga4gh-wes-spec-1.1.0.yml ===


GA4GH_WES_SCHEMAS = GA4GH_WES_SPEC["components"]["schemas"]


class WorkflowTypeVersion(BaseModel):
    workflow_type_version: list[str] | None = Field(
        [],
        description=GA4GH_WES_SCHEMAS["WorkflowTypeVersion"]["properties"]["workflow_type_version"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["WorkflowTypeVersion"]["description"],
        }
    )


class WorkflowEngineVersion(BaseModel):
    workflow_engine_version: list[str] | None = Field(
        [],
        description=GA4GH_WES_SCHEMAS["WorkflowEngineVersion"]["properties"]["workflow_engine_version"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["WorkflowEngineVersion"]["description"],
        }
    )


class DefaultWorkflowEngineParameter(BaseModel):
    name: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["DefaultWorkflowEngineParameter"]["properties"]["name"]["description"],
    )
    type: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["DefaultWorkflowEngineParameter"]["properties"]["type"]["description"],
    )
    default_value: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["DefaultWorkflowEngineParameter"]["properties"]["default_value"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["DefaultWorkflowEngineParameter"]["description"],
        }
    )


class ServiceInfo(Service):
    workflow_type_versions: dict[str, WorkflowTypeVersion] = Field(...)
    supported_wes_versions: list[str] = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ServiceInfo"]["allOf"][1]["properties"]["supported_wes_versions"]["description"],
    )
    supported_filesystem_protocols: list[str] = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ServiceInfo"]["allOf"][1]["properties"]["supported_filesystem_protocols"][
            "description"
        ],
    )
    workflow_engine_versions: dict[str, WorkflowEngineVersion] = Field(...)
    default_workflow_engine_parameters: dict[str, list[DefaultWorkflowEngineParameter]] = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ServiceInfo"]["allOf"][1]["properties"]["default_workflow_engine_parameters"][
            "description"
        ]
        + """\n
**sapporo-wes-2.0.0 extension:**

- original wes-1.1.0: List[DefaultWorkflowEngineParameter]
- sapporo-wes-2.0.0: Dict[str, List[DefaultWorkflowEngineParameter]]
""",
    )
    system_state_counts: dict[str, int] = Field(...)
    auth_instructions_url: HttpUrl = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ServiceInfo"]["allOf"][1]["properties"]["auth_instructions_url"]["description"],
    )
    tags: dict[str, str] = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["ServiceInfo"]["allOf"][1]["properties"]["tags"]["additionalProperties"][
            "description"
        ],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "org.sapporo.service",
                "name": "Sapporo WES",
                "type": {"group": "org.ga4gh", "artifact": "wes", "version": "1.1.0"},
                "organization": {"name": "Sapporo Project", "url": "https://github.com/sapporo-wes"},
                "version": "2.0.0",
                "workflow_type_versions": {"CWL": {"workflow_type_version": ["v1.0", "v1.1", "v1.2"]}},
                "supported_wes_versions": ["1.0.0", "1.1.0"],
                "supported_filesystem_protocols": ["http", "https", "file"],
                "workflow_engine_versions": {"cwltool": {"workflow_engine_version": ["3.1"]}},
                "default_workflow_engine_parameters": {},
                "system_state_counts": {"COMPLETE": 10, "RUNNING": 2, "QUEUED": 0},
                "auth_instructions_url": "https://github.com/sapporo-wes/sapporo-service#authentication",
                "tags": {},
            }
        }
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
    state: State | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["State"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["RunStatus"]["description"],
        }
    )


class RunSummary(RunStatus):
    start_time: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunSummary"]["allOf"][1]["properties"]["start_time"]["description"],
    )
    end_time: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunSummary"]["allOf"][1]["properties"]["end_time"]["description"],
    )
    tags: dict[str, str] = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["RunSummary"]["allOf"][1]["properties"]["tags"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["RunSummary"]["description"],
        }
    )


class RunListResponse(BaseModel):
    runs: list[RunStatus] | list[RunSummary] | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunListResponse"]["properties"]["runs"]["description"],
    )
    next_page_token: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunListResponse"]["properties"]["next_page_token"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["RunListResponse"]["description"],
            "example": {
                "runs": [
                    {
                        "run_id": "abc123-def456-ghi789",
                        "state": "COMPLETE",
                        "start_time": "2024-01-15T10:30:00Z",
                        "end_time": "2024-01-15T10:35:00Z",
                        "tags": {"project": "example"},
                    }
                ],
                "next_page_token": None,
            },
        }
    )


class RunRequest(BaseModel):
    workflow_params: dict[str, Any] | str = Field(
        ...,
        description=GA4GH_WES_SCHEMAS["RunRequest"]["properties"]["workflow_params"]["description"]
        + """\n
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
    tags: dict[str, str] | None = Field(None)
    workflow_engine: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunRequest"]["properties"]["workflow_engine"]["description"],
    )
    workflow_engine_version: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunRequest"]["properties"]["workflow_engine_version"]["description"],
    )
    workflow_engine_parameters: dict[str, str] | None = Field(None)
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
    name: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["name"]["description"],
    )
    cmd: list[str] | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["cmd"]["description"],
    )
    start_time: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["start_time"]["description"],
    )
    end_time: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["end_time"]["description"],
    )
    stdout: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["stdout"]["description"],
    )
    stderr: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["stderr"]["description"],
    )
    exit_code: int | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["Log"]["properties"]["exit_code"]["description"],
    )
    system_logs: list[str] | None = Field(
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
    system_logs: list[str] | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["TaskLog"]["allOf"][1]["properties"]["system_logs"]["description"],
    )
    tes_uri: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["TaskLog"]["allOf"][1]["properties"]["tes_uri"]["description"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": GA4GH_WES_SCHEMAS["TaskLog"]["description"],
        }
    )


class RunLog(BaseModel):
    run_id: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunLog"]["properties"]["run_id"]["description"],
    )
    request: RunRequest | None = Field(None)
    state: State | None = Field(None)
    run_log: Log | None = Field(None)
    task_logs_url: str | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunLog"]["properties"]["task_logs_url"]["description"],
    )
    task_logs: list[Log | TaskLog] | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunLog"]["properties"]["task_logs"]["description"],
    )
    outputs: list[FileObject] | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["RunLog"]["properties"]["outputs"]["description"]
        + """\n
**sapporo-wes-2.0.0 extension:**

- original wes-1.1.0: Optional[Dict[str, Any]]
- sapporo-wes-2.0.0: Optional[List[FileObject]]
""",
    )


class TaskListResponse(BaseModel):
    task_logs: list[TaskLog] | None = Field(
        None,
        description=GA4GH_WES_SCHEMAS["TaskListResponse"]["properties"]["task_logs"]["description"],
    )
    next_page_token: str | None = Field(
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
    """Schema for internal use as an intermediate representation of form data received by POST /runs.

    The schema of the form data sent to POST /runs and the schema of RunRequest used internally in the app are slightly different.
    Therefore, the form data is first converted to this intermediate RunRequestForm schema by sapporo.validator.validate_run_request before being transformed into RunRequest.
    """

    workflow_attachment: list[UploadFile]
    workflow_attachment_obj: list[FileObject]

    @field_serializer("workflow_attachment")
    def serialize_wf_attachment(self, value: list[UploadFile]) -> list[dict[str, Any]]:
        return [
            {
                "filename": file.filename,
                "size": file.size,
                "headers": dict(file.headers.items()),
                "content_type": file.content_type,
            }
            for file in value
        ]
