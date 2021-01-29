#!/usr/bin/env bash
set -Eeu

SCRIPT_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) &>/dev/null && pwd -P)

workflow_params="${SCRIPT_DIR}/workflow_params.json"

curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_name=CWL_trimming_and_qc_remote" \
  -F "workflow_params=<${workflow_params}" \
  -F "workflow_engine_name=cwltool" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs
