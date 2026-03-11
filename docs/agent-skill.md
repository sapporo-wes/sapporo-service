# Sapporo WES Agent Skill

LLM agent reference for running bioinformatics workflows via Sapporo WES using `curl`.

For the full request/response schema, see [`openapi/sapporo-wes-spec-2.1.0.yml`](../openapi/sapporo-wes-spec-2.1.0.yml) or the interactive docs at `$SAPPORO_ENDPOINT/docs`.

> **Tight on context?** Use [`docs/agent-quick-ref.md`](agent-quick-ref.md) — the essential 4 commands in ~40 lines.

## Prerequisites

- `curl` and `jq`
- `SAPPORO_ENDPOINT` set to the base URL (default: `http://localhost:1122`)

## Phase 0: Start a local server (if needed)

```bash
curl -s $SAPPORO_ENDPOINT/service-info | jq .workflow_engine_versions
```

If that fails, start with Docker Compose:

```bash
curl -O https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/compose.yml
docker compose up -d
```

## Phase 1: Submit a workflow

`POST /runs` accepts `application/json` (remote files) or `multipart/form-data` (local file upload). For the full list of fields and types, see the OpenAPI spec. The four required fields are `workflow_type`, `workflow_type_version`, `workflow_url`, and `workflow_engine`.

To find what engines and types your server supports:

```bash
curl -s $SAPPORO_ENDPOINT/service-info | jq '{engines: .workflow_engine_versions, types: .workflow_type_versions}'
```

Submit via JSON:

```bash
RUN_ID=$(curl -s -X POST $SAPPORO_ENDPOINT/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_type": "CWL",
    "workflow_type_version": "v1.0",
    "workflow_url": "https://example.com/workflow.cwl",
    "workflow_engine": "cwltool",
    "workflow_params": {"input": "https://example.com/data.txt"}
  }' | jq -r .run_id)
```

Submit via form (with local file upload):

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

## Phase 2: Poll until complete

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/status | jq -r .state
```

### State machine

```
QUEUED → INITIALIZING → RUNNING → COMPLETE
                               ↘ EXECUTOR_ERROR   (workflow engine failed — check stderr)
                               ↘ SYSTEM_ERROR     (infrastructure failure)
                               ↘ CANCELED
```

`CANCELING`, `DELETING`, and `DELETED` are transient/lifecycle states. All others are terminal.

Poll loop:

```bash
while true; do
  STATE=$(curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/status | jq -r .state)
  echo "State: $STATE"
  case $STATE in COMPLETE|EXECUTOR_ERROR|SYSTEM_ERROR|CANCELED) break ;; esac
  sleep 10
done
```

## Phase 3: Retrieve outputs

List output files (each entry has `file_name` and `file_url`):

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/outputs | jq .outputs
```

Download a specific file:

```bash
curl -s -o result.html "$SAPPORO_ENDPOINT/runs/$RUN_ID/outputs/qc_result.html"
```

Download all outputs as zip:

```bash
curl -s -o outputs.zip "$SAPPORO_ENDPOINT/runs/$RUN_ID/outputs?download=true"
```

RO-Crate provenance metadata:

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/ro-crate | jq .
```

## Error handling

On `EXECUTOR_ERROR` or `SYSTEM_ERROR`, check the run log:

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID | jq '{exit_code: .run_log.exit_code, stderr: .run_log.stderr}'
```

API errors (4xx/5xx) return `{"msg": "...", "status_code": N}`. Common ones:

- `400 Workflow is not in the executable workflows list` — check `GET /executable-workflows`
- `404 Run not found` — invalid `run_id`

## End-to-end example: CWL trimming + QC

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

# 3. Outputs
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/outputs | jq .
```

## End-to-end example: Nextflow hello world

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

## Authentication (when enabled)

```bash
TOKEN=$(curl -s -X POST $SAPPORO_ENDPOINT/token \
  -F "username=user1" -F "password=secret" | jq -r .access_token)

curl -s -H "Authorization: Bearer $TOKEN" $SAPPORO_ENDPOINT/runs | jq .
```

## References

- OpenAPI spec (interactive): `$SAPPORO_ENDPOINT/docs`
- OpenAPI YAML: [`openapi/sapporo-wes-spec-2.1.0.yml`](../openapi/sapporo-wes-spec-2.1.0.yml)
- WES compatibility: [`docs/wes-compatibility.md`](wes-compatibility.md)
- Configuration: [`docs/configuration.md`](configuration.md)
