#!/usr/bin/env bash
set -Eeu

SCRIPT_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) &>/dev/null && pwd -P)
RESOURCE_DIR="${SCRIPT_DIR}/../../../../resources/snakemake"

workflow_engine_parameters="${SCRIPT_DIR}/workflow_engine_parameters.json"

curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_name=snakemake_tutorial_wf" \
  -F "workflow_params={}" \
  -F "workflow_engine_name=snakemake" \
  -F "workflow_engine_parameters=<${workflow_engine_parameters}" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs
