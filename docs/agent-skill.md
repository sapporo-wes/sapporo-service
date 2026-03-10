# Sapporo WES Agent Skill

This document is designed to be pasted into an agent system prompt or referenced as a slash command. It gives an LLM agent the minimal context needed to run bioinformatics workflows via Sapporo WES using `curl`.

> **Tight on context?** Use [`docs/agent-quick-ref.md`](agent-quick-ref.md) instead — the essential 4 commands in ~40 lines.

## What this skill does

Submit bioinformatics workflows to a Sapporo WES server, poll until complete, and retrieve output files — all via GA4GH WES REST API calls using `curl`. No SDK required.

## Prerequisites

- `curl` and `jq` available in the shell
- `SAPPORO_ENDPOINT` set to the base URL (default: `http://localhost:1122`)
- Docker and Docker Compose installed (only needed to start a local server)

```bash
export SAPPORO_ENDPOINT=http://localhost:1122
```

---

## Phase 0: Start a local server (if needed)

Check if a server is already running:

```bash
curl -s $SAPPORO_ENDPOINT/service-info | jq .workflow_engine_versions
```

If the request fails, start one with Docker Compose:

```bash
curl -O https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/compose.yml
docker compose up -d
```

Verify the service is healthy:

```bash
curl -s $SAPPORO_ENDPOINT/service-info | jq '{engines: .workflow_engine_versions, types: .workflow_type_versions}'
```

The service exposes an interactive API at `$SAPPORO_ENDPOINT/docs`.

---

## Phase 1: Submit a workflow

`POST /runs` accepts either `multipart/form-data` (with file uploads) or `application/json` (remote files only).

### Required fields

| Field | Description |
|---|---|
| `workflow_type` | `CWL`, `WDL`, `NFL` (Nextflow), or `SMK` (Snakemake) |
| `workflow_type_version` | e.g. `v1.0`, `v1.2`, `draft-2`, `DSL2` |
| `workflow_url` | URL of the workflow file |
| `workflow_engine` | `cwltool`, `cromwell`, `nextflow`, `snakemake`, `toil`, `ep3` |

### Submit via JSON (recommended for remote workflows)

```bash
RUN_ID=$(curl -s -X POST $SAPPORO_ENDPOINT/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_type": "CWL",
    "workflow_type_version": "v1.0",
    "workflow_url": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimming_and_qc_remote.cwl",
    "workflow_engine": "cwltool",
    "workflow_params": {
      "fastq_1": {
        "class": "File",
        "location": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/ERR034597_1.small.fq.gz"
      },
      "fastq_2": {
        "class": "File",
        "location": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/ERR034597_2.small.fq.gz"
      }
    }
  }' | jq -r .run_id)
echo "Run ID: $RUN_ID"
```

### Submit via multipart form (for local file upload)

```bash
RUN_ID=$(curl -s -X POST $SAPPORO_ENDPOINT/runs \
  -F "workflow_type=CWL" \
  -F "workflow_type_version=v1.0" \
  -F "workflow_url=https://example.com/workflow.cwl" \
  -F "workflow_engine=cwltool" \
  -F 'workflow_params={"input": "data.txt"}' \
  -F "workflow_attachment=@local_file.txt" \
  | jq -r .run_id)
```

### Tag a run for later filtering

Add a `tags` JSON map to any submission:

```bash
# In JSON body:
"tags": {"project": "rnaseq", "sample": "ERR034597"}

# In form data:
-F 'tags={"project": "rnaseq"}'
```

---

## Phase 2: Poll until complete

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/status | jq .
# {"run_id": "...", "state": "RUNNING"}
```

### Run state machine

```
QUEUED → INITIALIZING → RUNNING → COMPLETE
                                ↘ EXECUTOR_ERROR
                                ↘ SYSTEM_ERROR
                                ↘ CANCELED
```

| State | Meaning |
|---|---|
| `QUEUED` | Accepted, waiting to start |
| `INITIALIZING` | Setting up execution environment |
| `RUNNING` | Workflow engine is executing |
| `COMPLETE` | Finished successfully |
| `EXECUTOR_ERROR` | Workflow engine reported an error (check stderr) |
| `SYSTEM_ERROR` | Infrastructure-level failure |
| `CANCELED` | Canceled by `POST /runs/{run_id}/cancel` |
| `CANCELING` | Cancel in progress |
| `DELETED` / `DELETING` | Run was deleted |

### Poll loop (shell)

```bash
while true; do
  STATE=$(curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/status | jq -r .state)
  echo "State: $STATE"
  case $STATE in
    COMPLETE|EXECUTOR_ERROR|SYSTEM_ERROR|CANCELED) break ;;
  esac
  sleep 10
done
```

---

## Phase 3: Inspect outputs

Get the full run log (request, state, stdout/stderr, outputs):

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID | jq .
```

List output files:

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/outputs | jq .outputs
# [{"file_name": "qc_result.html", "file_url": "http://localhost:1122/runs/.../outputs/qc_result.html"}]
```

Download a specific output file:

```bash
curl -s -o result.html "$SAPPORO_ENDPOINT/runs/$RUN_ID/outputs/qc_result.html"
```

Download all outputs as a zip:

```bash
curl -s -o outputs.zip "$SAPPORO_ENDPOINT/runs/$RUN_ID/outputs?download=true"
```

Get RO-Crate provenance metadata:

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/ro-crate | jq .
```

---

## Error handling

When a run fails (`EXECUTOR_ERROR` or `SYSTEM_ERROR`), check stderr from the run log:

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID | jq '.run_log.stderr'
```

Also check exit code:

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID | jq '.run_log.exit_code'
```

For 4xx/5xx HTTP errors from the API itself, the response body contains:

```json
{"msg": "error description", "status_code": 400}
```

Common causes:
- `400 workflow_type is required` — missing required field
- `400 workflow_url is required` — workflow URL not provided
- `400 Workflow is not in the executable workflows list` — server restricts runnable workflows; check `GET /executable-workflows`
- `404 Run not found` — invalid run_id

---

## Other useful endpoints

Check available engines and workflow types:

```bash
curl -s $SAPPORO_ENDPOINT/service-info | jq '{engines: .workflow_engine_versions, types: .workflow_type_versions}'
```

List recent runs (newest first):

```bash
curl -s "$SAPPORO_ENDPOINT/runs?page_size=10&sort_order=desc" | jq '.runs[] | {run_id, state, start_time}'
```

Filter runs by state:

```bash
curl -s "$SAPPORO_ENDPOINT/runs?state=COMPLETE" | jq .total_runs
```

Filter runs by tag:

```bash
curl -s "$SAPPORO_ENDPOINT/runs?tags=project:rnaseq" | jq '.runs[].run_id'
```

Cancel a running run:

```bash
curl -s -X POST $SAPPORO_ENDPOINT/runs/$RUN_ID/cancel | jq .
```

Delete a run and its files:

```bash
curl -s -X DELETE $SAPPORO_ENDPOINT/runs/$RUN_ID | jq .
```

---

## Supported engine / workflow type combinations (default run.sh)

| Engine | Workflow Type | Notes |
|---|---|---|
| `cwltool` | `CWL` | |
| `toil` | `CWL` | |
| `ep3` | `CWL` | |
| `cromwell` | `WDL` | |
| `nextflow` | `NFL` | Use `workflow_type_version: DSL2` |
| `snakemake` | `SMK` | |

---

## Example: CWL trimming + QC (cwltool)

End-to-end example using a public test workflow:

```bash
export SAPPORO_ENDPOINT=http://localhost:1122

# 1. Submit
RUN_ID=$(curl -s -X POST $SAPPORO_ENDPOINT/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_type": "CWL",
    "workflow_type_version": "v1.0",
    "workflow_url": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimming_and_qc_remote.cwl",
    "workflow_engine": "cwltool",
    "workflow_params": {
      "fastq_1": {"class": "File", "location": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/ERR034597_1.small.fq.gz"},
      "fastq_2": {"class": "File", "location": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/ERR034597_2.small.fq.gz"}
    }
  }' | jq -r .run_id)
echo "Submitted: $RUN_ID"

# 2. Poll
while true; do
  STATE=$(curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/status | jq -r .state)
  echo "State: $STATE"
  case $STATE in COMPLETE|EXECUTOR_ERROR|SYSTEM_ERROR|CANCELED) break ;; esac
  sleep 10
done

# 3. Retrieve outputs
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/outputs | jq .
```

## Example: Nextflow hello world

```bash
RUN_ID=$(curl -s -X POST $SAPPORO_ENDPOINT/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_type": "NFL",
    "workflow_type_version": "DSL2",
    "workflow_url": "https://raw.githubusercontent.com/nextflow-io/hello/master/main.nf",
    "workflow_engine": "nextflow"
  }' | jq -r .run_id)
```

---

## Authentication (when enabled)

Get a token:

```bash
TOKEN=$(curl -s -X POST $SAPPORO_ENDPOINT/token \
  -F "username=user1" \
  -F "password=secret" | jq -r .access_token)
```

Use the token in subsequent requests:

```bash
curl -s -H "Authorization: Bearer $TOKEN" $SAPPORO_ENDPOINT/runs | jq .
```

---

## References

- OpenAPI spec (interactive): `$SAPPORO_ENDPOINT/docs`
- OpenAPI YAML: `openapi/sapporo-wes-spec-2.1.0.yml` in this repo
- WES compatibility details: `docs/wes-compatibility.md`
- Configuration options: `docs/configuration.md`
