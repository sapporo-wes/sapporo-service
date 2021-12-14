#!/usr/bin/env bash
set -Eeu

SCRIPT_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) &>/dev/null && pwd -P)

workflow_params="${SCRIPT_DIR}/workflow_params.json"
workflow_engine_parameters="${SCRIPT_DIR}/workflow_engine_parameters.json"
workflow="${SCRIPT_DIR}/../../../../resources/nextflow/params_outdir.nf"

curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_params=<${workflow_params}" \
  -F "workflow_type=NFL" \
  -F "workflow_type_version=1.0" \
  -F "workflow_url=./params_outdir.nf" \
  -F "workflow_engine_name=nextflow" \
  -F "workflow_engine_parameters=<${workflow_engine_parameters}" \
  -F "workflow_attachment[]=@${workflow}" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs
