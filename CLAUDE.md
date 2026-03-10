# sapporo-service — Claude Code Context

Sapporo is a GA4GH WES implementation that runs bioinformatics workflows (CWL, WDL, Nextflow, Snakemake) via a REST API. Each engine runs in its own Docker container.

## Running workflows as an agent

Use the slash command `/run-wes-workflow` to submit a workflow and retrieve outputs interactively.

For the full interaction reference (all curl examples, state machine, error handling, auth):

```
docs/agent-skill.md
```

Quick-reference (minimal context budget):

```
docs/agent-quick-ref.md
```

## Key API endpoints (default: http://localhost:1122)

| Method | Path | Purpose |
|---|---|---|
| GET | `/service-info` | List supported engines and workflow types |
| POST | `/runs` | Submit a workflow (JSON or multipart) |
| GET | `/runs/{id}/status` | Poll run state |
| GET | `/runs/{id}` | Full run log (stdout, stderr, outputs) |
| GET | `/runs/{id}/outputs` | List output files |
| GET | `/runs/{id}/outputs/{path}` | Download a specific output file |
| GET | `/runs/{id}/ro-crate` | RO-Crate provenance metadata |

## Start the service

```bash
docker compose up -d
curl localhost:1122/service-info | jq .workflow_engine_versions
```

## Key files

- `sapporo/routers.py` — all route handlers
- `sapporo/schemas.py` — request/response models
- `openapi/sapporo-wes-spec-2.1.0.yml` — full OpenAPI spec
- `sapporo/run.sh` — workflow engine dispatch script
- `sapporo/service_info.json` — default service metadata
