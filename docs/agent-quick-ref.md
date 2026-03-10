# Sapporo WES — Quick Reference

Endpoint: `export SAPPORO_ENDPOINT=http://localhost:1122`

## 1. Check service

```bash
curl -s $SAPPORO_ENDPOINT/service-info | jq '{engines: .workflow_engine_versions, types: .workflow_type_versions}'
```

## 2. Submit

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

Required fields: `workflow_type`, `workflow_type_version`, `workflow_url`, `workflow_engine`.

## 3. Poll

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/status | jq -r .state
# QUEUED → INITIALIZING → RUNNING → COMPLETE | EXECUTOR_ERROR | SYSTEM_ERROR
```

## 4. Outputs

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID/outputs | jq .outputs          # list
curl -s -o out.zip "$SAPPORO_ENDPOINT/runs/$RUN_ID/outputs?download=true"  # zip
curl -s -o file.txt "$SAPPORO_ENDPOINT/runs/$RUN_ID/outputs/file.txt"      # single file
```

## On error

```bash
curl -s $SAPPORO_ENDPOINT/runs/$RUN_ID | jq '{exit_code: .run_log.exit_code, stderr: .run_log.stderr}'
```

## Engine / type table

| Engine | Type | Version |
|---|---|---|
| `cwltool` | `CWL` | `v1.0`, `v1.2` |
| `cromwell` | `WDL` | `1.0` |
| `nextflow` | `NFL` | `DSL2` |
| `snakemake` | `SMK` | `v1` |

Full reference: `docs/agent-skill.md`
