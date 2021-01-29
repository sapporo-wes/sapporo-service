#!/usr/bin/env bash
set -Eeu

SCRIPT_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) &>/dev/null && pwd -P)

workflow_params="${SCRIPT_DIR}/workflow_params.json"
workflow="${SCRIPT_DIR}/../../../../resources/nextflow/str_input.nf"

curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_params=<${workflow_params}" \
  -F "workflow_type=Nextflow" \
  -F "workflow_type_version=v1.0" \
  -F "workflow_url=./str_input.nf" \
  -F "workflow_engine_name=nextflow" \
  -F "workflow_attachment[]=@${workflow}" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs
