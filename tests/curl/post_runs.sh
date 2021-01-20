#!/usr/bin/env bash
set -Eeu

if [[ $# < 4 ]]; then
  echo "[Error] Usage: $(basename ${BASH_SOURCE[0]}) workflow_name workflow_params_file workflow_engine_name workflow_engine_params_file tags_file(optional)"
  exit 1
elif [[ $# == 4 ]]; then
  curl -fsSL -X POST \
    -H "Content-Type: multipart/form-data" \
    -F "workflow_name=$1:" \
    -F "workflow_params=<$2" \
    -F "workflow_engine_name=$3" \
    -F "workflow_engine_params=<$4" \
    http://localhost:${SAPPORO_PORT}/runs
elif [[ $# == 5 ]]; then
  curl -fsSL -X POST \
    -H "Content-Type: multipart/form-data" \
    -F "workflow_name=$1:" \
    -F "workflow_params=<$2" \
    -F "workflow_engine_name=$3" \
    -F "workflow_engine_params=<$4" \
    -F "tags=<$5" \
    http://localhost:${SAPPORO_PORT}/runs
else
  echo "[Error] Usage: $(basename ${BASH_SOURCE[0]}) workflow_name workflow_params_file workflow_engine_name workflow_engine_params_file tags_file(optional)"
  exit 1
fi
