#!/usr/bin/env bash
set -Eeu

SCRIPT_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) &>/dev/null && pwd -P)

workflow_params="${SCRIPT_DIR}/workflow_params.json"

curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_name=nextflow_file_input" \
  -F "workflow_params=<${workflow_params}" \
  -F "workflow_engine_name=nextflow" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs
