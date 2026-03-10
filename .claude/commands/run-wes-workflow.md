# Run a WES Workflow via Sapporo

Submit a workflow to a Sapporo WES server, wait for it to complete, and retrieve the output files.

## Instructions for the agent

You are running a bioinformatics workflow via Sapporo WES. Follow these steps in order using `curl`. Use `jq` to parse JSON responses.

### Step 1: Confirm the endpoint

Check the environment variable `SAPPORO_ENDPOINT`. If unset, default to `http://localhost:1122`.

```bash
export SAPPORO_ENDPOINT=${SAPPORO_ENDPOINT:-http://localhost:1122}
curl -s $SAPPORO_ENDPOINT/service-info | jq '{engines: .workflow_engine_versions, types: .workflow_type_versions}'
```

If this fails, the service is not running. Start it:

```bash
docker compose up -d   # requires compose.yml in the current directory
```

### Step 2: Get workflow details from the user

Ask the user for (or read from context):
- `workflow_url` — URL of the workflow file (required)
- `workflow_type` — `CWL`, `WDL`, `NFL`, or `SMK` (required)
- `workflow_type_version` — e.g. `v1.0`, `DSL2` (required)
- `workflow_engine` — `cwltool`, `cromwell`, `nextflow`, `snakemake` (required)
- `workflow_params` — JSON object or YAML string of input parameters (optional)

### Step 3: Submit the workflow

```bash
RUN_ID=$(curl -s -X POST $SAPPORO_ENDPOINT/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_type": "<TYPE>",
    "workflow_type_version": "<VERSION>",
    "workflow_url": "<URL>",
    "workflow_engine": "<ENGINE>",
    "workflow_params": <PARAMS_JSON_OR_NULL>
  }' | jq -r .run_id)
echo "Submitted run: $RUN_ID"
```

### Step 4: Poll until complete

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

Terminal states: `COMPLETE` (success), `EXECUTOR_ERROR` / `SYSTEM_ERROR` (failure), `CANCELED`.

### Step 5: Handle errors

If the run ended in an error state:

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID | jq '{state, exit_code: .run_log.exit_code, stderr: .run_log.stderr}'
```

Report the stderr output and exit code to the user.

### Step 6: Retrieve outputs (on COMPLETE)

List output files:

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/outputs | jq .outputs
```

Download all outputs as zip:

```bash
curl -s -o outputs.zip "$SAPPORO_ENDPOINT/runs/$RUN_ID/outputs?download=true"
```

Download a specific file (replace `<path>` with `file_name` from the outputs list):

```bash
curl -s -o <filename> "$SAPPORO_ENDPOINT/runs/$RUN_ID/outputs/<path>"
```

### Reference: engine / workflow type combinations

| Engine | Workflow Type | `workflow_type_version` |
|---|---|---|
| `cwltool` | `CWL` | `v1.0`, `v1.1`, `v1.2` |
| `toil` | `CWL` | `v1.0`, `v1.2` |
| `ep3` | `CWL` | `v1.0` |
| `cromwell` | `WDL` | `draft-2`, `1.0` |
| `nextflow` | `NFL` | `DSL2` |
| `snakemake` | `SMK` | `v1` |

### Reference: run states

```
QUEUED → INITIALIZING → RUNNING → COMPLETE
                               ↘ EXECUTOR_ERROR
                               ↘ SYSTEM_ERROR
```

See `docs/agent-skill.md` in this repo for the full skill reference.
