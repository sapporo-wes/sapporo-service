#!/usr/bin/env bash
set -Eeu

SCRIPT_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) &>/dev/null && pwd -P)

workflow_params="${SCRIPT_DIR}/workflow_params.json"

curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_params=<${workflow_params}" \
  -F "workflow_type=CWL" \
  -F "workflow_type_version=v1.0" \
  -F "workflow_url=https://raw.githubusercontent.com/ddbj/SAPPORO-service/master/tests/resources/cwltool/trimming_and_qc_remote.cwl" \
  -F "workflow_engine_name=cwltool" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs
