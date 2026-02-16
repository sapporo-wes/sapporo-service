# WES Compatibility

This document describes the compatibility between [GA4GH WES 1.1.0](https://ga4gh.github.io/workflow-execution-service-schemas/), sapporo-wes 2.0.0, and sapporo-wes 2.1.0.

```
+-------------+    partial    +-----------------+   evolution   +-----------------+
|  WES 1.1.0  |<-- compat --->|  sapporo 2.0.0  |-------------->|  sapporo 2.1.0  |
|  (standard) |               |     (prev)      |               |    (current)    |
+-------------+               +-----------------+               +-----------------+
```

- **WES 1.1.0 <-> sapporo 2.0.0**: Partially compatible. sapporo extends WES with multi-engine support, structured outputs, and additional endpoints, but introduces 2 breaking schema changes.
- **sapporo 2.0.0 -> sapporo 2.1.0**: Evolutionary upgrade. Stricter input validation, new query/filtering capabilities, and `application/json` request support. One minor breaking change (`POST /runs` required fields).

## OpenAPI Specifications

| Spec | YAML | SwaggerUI |
|---|---|---|
| WES 1.1.0 | [`workflow_execution_service.openapi.yaml`](https://github.com/ga4gh/workflow-execution-service-schemas/blob/1.1.0/openapi/workflow_execution_service.openapi.yaml) | [View](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/ga4gh/workflow-execution-service-schemas/1.1.0/openapi/workflow_execution_service.openapi.yaml) |
| sapporo 2.0.0 | [`openapi/sapporo-wes-spec-2.0.0.yml`](https://github.com/sapporo-wes/sapporo-service/blob/main/openapi/sapporo-wes-spec-2.0.0.yml) | [View](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/openapi/sapporo-wes-spec-2.0.0.yml) |
| sapporo 2.1.0 | [`openapi/sapporo-wes-spec-2.1.0.yml`](https://github.com/sapporo-wes/sapporo-service/blob/main/openapi/sapporo-wes-spec-2.1.0.yml) | [View](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/openapi/sapporo-wes-spec-2.1.0.yml) |

When the service is running, access `http://localhost:1122/docs` to explore the API interactively.

## WES 1.1.0 <-> sapporo 2.0.0

### Summary

| # | Category | Item | WES 1.1.0 | sapporo 2.0.0 | Rationale | Related |
|---|---|---|---|---|---|---|
| 1-1 | Breaking | `ServiceInfo.default_workflow_engine_parameters` | `List[Param]` | `Dict[str, List[Param]]` | Multi-engine support requires engine-keyed parameters | [#185](https://github.com/ga4gh/workflow-execution-service-schemas/issues/185), [#220](https://github.com/ga4gh/workflow-execution-service-schemas/issues/220) |
| 1-2 | Breaking | `RunLog.outputs` | `Dict[str, Any]` | `List[FileObject] \| null` | Structured output with downloadable URLs | [#226](https://github.com/ga4gh/workflow-execution-service-schemas/pull/226), [#228](https://github.com/ga4gh/workflow-execution-service-schemas/issues/228) |
| 2-1 | Constraint | `POST /runs` `workflow_type` | optional (form) | **required** | Cannot execute without specifying type | - |
| 2-2 | Constraint | `POST /runs` `workflow_engine` | optional | **required** | Cannot execute without specifying engine | - |
| 2-3 | Constraint | `POST /runs` `requestBody` | `required: false` | `required: true` | Empty POST is meaningless | - |
| 2-4 | Constraint | `ErrorResponse` fields | optional | required | Consistent error responses | - |
| 2-5 | Constraint | `auth_instructions_url` | `string` | `string (format: uri)` | URL field should validate as URL | - |
| 3-1 | Additive | `State` enum | 11 values | +`DELETED`, `DELETING` | Support for run deletion lifecycle | [#218](https://github.com/ga4gh/workflow-execution-service-schemas/issues/218) |
| 3-2 | Additive | `workflow_params` type | `object` only | `object \| string` | Accommodate multipart form-data encoding | - |
| 3-3 | Additive | `GET /runs` query params | `page_size`, `page_token` | +`sort_order`, `state`, `run_ids`, `latest` | Filtering and sorting support | [#220](https://github.com/ga4gh/workflow-execution-service-schemas/issues/220), [#230](https://github.com/ga4gh/workflow-execution-service-schemas/issues/230) |
| 3-4 | Additive | `POST /runs` form field | - | `workflow_attachment_obj` | Remote file download via URL | [#224](https://github.com/ga4gh/workflow-execution-service-schemas/issues/224) |
| 4-1 | Unimplemented | `GET /runs/{run_id}/tasks` | defined | returns 400 | Not planned; structural limitation (DinD) | - |
| 4-2 | Unimplemented | `GET /runs/{run_id}/tasks/{task_id}` | defined | returns 400 | Same as above | - |

### 1-1. `ServiceInfo.default_workflow_engine_parameters` (Breaking)

Type changed from flat array to object keyed by engine name.

```json
// WES 1.1.0: List[DefaultWorkflowEngineParameter]
{
  "default_workflow_engine_parameters": [
    { "name": "--outdir", "type": "string", "default_value": "/tmp" }
  ]
}

// sapporo 2.0.0: Dict[str, List[DefaultWorkflowEngineParameter]]
{
  "default_workflow_engine_parameters": {
    "cwltool": [
      { "name": "--outdir", "type": "string", "default_value": "/tmp" }
    ],
    "nextflow": []
  }
}
```

### 1-2. `RunLog.outputs` (Breaking)

Type changed from free-form object to array of `FileObject`.

```json
// WES 1.1.0: Dict[str, Any]
{
  "outputs": {
    "output.txt": "s3://bucket/output.txt"
  }
}

// sapporo 2.0.0: List[FileObject] | null
{
  "outputs": [
    {
      "file_name": "output.txt",
      "file_url": "http://localhost:1122/runs/abc123/outputs/output.txt"
    }
  ]
}
```

### 2-1 - 2-5. Constraint Changes

**`POST /runs` required fields (2-1, 2-2, 2-3):**

WES 1.1.0 form schema has no `required` list (all optional). sapporo enforces `workflow_type` and `workflow_engine` as required, and sets `requestBody.required: true`.

| Form field | WES 1.1.0 (form) | WES 1.1.0 (`RunRequest`) | sapporo 2.0.0 (form) |
|---|---|---|---|
| `workflow_type` | optional | **required** | **required** |
| `workflow_type_version` | optional | **required** | optional |
| `workflow_url` | optional | **required** | optional |
| `workflow_engine` | optional | optional | **required** |

**`ErrorResponse` required fields (2-4):**

```
WES 1.1.0:      { msg?: string, status_code?: int }  // both optional
sapporo 2.0.0:  { msg: string, status_code: int }    // both required
```

**`auth_instructions_url` validation (2-5):**

```
WES 1.1.0:      string                // any string
sapporo 2.0.0:  string (format: uri)  // validated as URL
```

### 3-1 - 3-4. Additive Changes

**`State` enum (3-1):**

sapporo adds `DELETED` and `DELETING` to support the run deletion lifecycle via `DELETE /runs/{run_id}`.

```
WES 1.1.0 (11 values):
  UNKNOWN, QUEUED, INITIALIZING, RUNNING, PAUSED, COMPLETE,
  EXECUTOR_ERROR, SYSTEM_ERROR, CANCELED, CANCELING, PREEMPTED

sapporo 2.0.0 (13 values):
  ... all of the above, plus: DELETED, DELETING
```

**`workflow_params` accepts string (3-2):**

```
WES 1.1.0:      Dict[str, Any]        // object only
sapporo 2.0.0:  Dict[str, Any] | str  // object or JSON string
```

**`GET /runs` additional query parameters (3-3):**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `sort_order` | `"asc" \| "desc"` | `"desc"` | Sort by `start_time` |
| `state` | `State \| null` | `null` | Filter by run state |
| `run_ids` | `List[str] \| null` | `null` | Filter by specific run IDs |
| `latest` | `bool \| null` | `false` | Return live state instead of snapshot |

**`POST /runs` `workflow_attachment_obj` (3-4):**

Optional field containing a JSON array of `FileObject` to download remote files:

```json
[
  { "file_name": "path/to/file", "file_url": "https://example.com/file" }
]
```

### Unimplemented Endpoints

| Endpoint | WES 1.1.0 operation | sapporo status |
|---|---|---|
| `GET /runs/{run_id}/tasks` | `ListTasks` | Not implemented (returns 400). No plans to implement. |
| `GET /runs/{run_id}/tasks/{task_id}` | `GetTask` | Not implemented (returns 400). No plans to implement. |

### sapporo-only Extensions

**Additional endpoints:**

| Endpoint | Method | Description |
|---|---|---|
| `/runs/{run_id}` | `DELETE` | Delete a run and its associated files |
| `/executable-workflows` | `GET` | List workflows the service can execute |
| `/runs/{run_id}/outputs` | `GET` | List output files or download as zip |
| `/runs/{run_id}/outputs/{path}` | `GET` | Download a specific output file |
| `/runs/{run_id}/ro-crate` | `GET` | Download RO-Crate metadata or zip |
| `/token` | `POST` | Authenticate and obtain a JWT token |
| `/me` | `GET` | Return authenticated user information |

**Additional schemas:**

| Schema | Description |
|---|---|
| `FileObject` | `{ file_name: str, file_url: str }` |
| `OutputsListResponse` | `{ outputs: List[FileObject] }` |
| `ExecutableWorkflows` | `{ workflows: List[str] }` |
| `TokenResponse` | `{ access_token: str, token_type: str }` |
| `MeResponse` | `{ username: str }` |

**Behavioral differences:**

| Behavior | Description |
|---|---|
| `GET /runs` snapshot mode | Returns a snapshot aggregated periodically, not live state |
| `GET /runs/{run_id}` live state | Always reads the run directory and returns the latest state |
| `system_state_counts` user scoping | When authenticated, counts only the authenticated user's runs |

## sapporo 2.0.0 -> sapporo 2.1.0

### Summary

| # | Category | Item | sapporo 2.0.0 | sapporo 2.1.0 | Rationale | Related |
|---|---|---|---|---|---|---|
| A-1 | Constraint | `POST /runs` `workflow_type_version` | optional | **required** | Implicit auto-selection from service-info is error-prone | WES `RunRequest` requires it |
| A-2 | Constraint | `POST /runs` `workflow_url` | optional | **required** | Entry workflow must be explicit, even with `workflow_attachment` | WES `RunRequest` requires it |
| B-1 | Feature | `total_runs` in `RunListResponse` | not present | added | Total count for pagination | [#183](https://github.com/ga4gh/workflow-execution-service-schemas/pull/183) (merged to WES develop) |
| B-2 | Feature | `POST /runs` `application/json` | `multipart/form-data` only | +`application/json` | Better DX; structured request without file upload | [#226](https://github.com/ga4gh/workflow-execution-service-schemas/pull/226) |
| B-3 | Feature | `GET /runs` tag filtering | not present | `?tags=key:value` (repeatable, AND) | Tags are settable but not searchable in 2.0.0 | [#213](https://github.com/ga4gh/workflow-execution-service-schemas/pull/213) |
| B-4 | Feature | `DELETE /runs` bulk delete | not present | `DELETE /runs?run_ids=id1&run_ids=id2` | No way to delete multiple runs at once | [#218](https://github.com/ga4gh/workflow-execution-service-schemas/issues/218) |
| B-5 | Feature | `GET /runs/{run_id}/outputs` `name` param | not present | `?download=true&name=my_project` | ZIP file/dir name customization for downstream use | sapporo-only |

### A-1, A-2. `POST /runs` Required Fields (Breaking)

`workflow_type_version` and `workflow_url` are now required in the `POST /runs` form.

| Form field | sapporo 2.0.0 | sapporo 2.1.0 |
|---|---|---|
| `workflow_type` | **required** | **required** |
| `workflow_type_version` | optional (auto-selected from service-info) | **required** |
| `workflow_url` | optional (empty string fallback) | **required** |
| `workflow_engine` | **required** | **required** |

**Migration:** Clients must explicitly provide `workflow_type_version` and `workflow_url`. For `workflow_attachment` uploads, use a relative path as `workflow_url`.

### B-1. `total_runs` in `RunListResponse`

Added `total_runs` field to `RunListResponse` for pagination support. This aligns with WES [#183](https://github.com/ga4gh/workflow-execution-service-schemas/pull/183) which has been merged to the WES develop branch.

```json
{
  "runs": [...],
  "next_page_token": "...",
  "total_runs": 42
}
```

### B-2. `POST /runs` `application/json` Support

`POST /runs` now accepts `application/json` in addition to `multipart/form-data`. The Content-Type header determines request parsing:

- **`multipart/form-data`**: For requests with file uploads via `workflow_attachment` (unchanged from 2.0.0).
- **`application/json`**: For requests without file uploads. Use `workflow_url` and `workflow_attachment_obj` for remote files.

```json
POST /runs
Content-Type: application/json

{
  "workflow_type": "CWL",
  "workflow_type_version": "v1.0",
  "workflow_url": "https://example.com/workflow.cwl",
  "workflow_engine": "cwltool",
  "workflow_params": { "input": "https://example.com/data.txt" },
  "workflow_attachment_obj": [
    { "file_name": "helper.cwl", "file_url": "https://example.com/helper.cwl" }
  ]
}
```

### B-3. `GET /runs` Tag Filtering

Added `tags` query parameter for filtering runs by tag key-value pairs. Multiple `tags` parameters can be specified and are combined with AND logic.

```
GET /runs?tags=project:genomics&tags=env:production
```

All existing filters (`state`, `run_ids`, `sort_order`) can be combined with `tags`. All filter parameters use AND logic.

### B-4. `DELETE /runs` Bulk Delete

Added `DELETE /runs` endpoint for bulk deletion. Requires `run_ids` query parameter; omitting it returns 400 to prevent accidental mass deletion.

```
DELETE /runs?run_ids=abc123&run_ids=def456
```

### B-5. `GET /runs/{run_id}/outputs` ZIP Name Customization

Added `name` query parameter to `GET /runs/{run_id}/outputs` for customizing the ZIP download name. This affects both the download file name and the root directory name inside the ZIP.

| Item | Default (`name` omitted) | Custom (`name=my_project`) |
|---|---|---|
| Download file name | `sapporo_{run_id}_outputs.zip` | `my_project.zip` |
| ZIP root directory | `sapporo_{run_id}_outputs/` | `my_project/` |

```
GET /runs/{run_id}/outputs?download=true&name=my_project
```

The `name` parameter is ignored when `download=false` (default). The value is sanitized to prevent path traversal.
