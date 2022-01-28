#!/usr/bin/env bash
set -Eeu

SCRIPT_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) &>/dev/null && pwd -P)
RESOURCE_DIR="${SCRIPT_DIR}/../../../../resources/cromwell/dockstore-tool-bamstats"

workflow_params="${RESOURCE_DIR}/test.json"
data="${RESOURCE_DIR}/tiny.bam"
tags="${SCRIPT_DIR}/tags.json"

curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_name=cromwell_bamstats_cwl" \
  -F "workflow_params=<${workflow_params}" \
  -F "workflow_engine_name=cromwell" \
  -F "tags=<${tags}" \
  -F "workflow_attachment=@${data}" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs
