#!/usr/bin/env bash
set -euo pipefail

# Define default values for SAPPORO_HOST and SAPPORO_PORT
SAPPORO_HOST=${SAPPORO_HOST:-127.0.0.1}
SAPPORO_PORT=${SAPPORO_PORT:-1122}

PACKAGE_ROOT="$(cd "$(dirname "$0")" && pwd)"
while [[ "${PACKAGE_ROOT}" != "/" && ! -f "${PACKAGE_ROOT}/pyproject.toml" ]]; do
  PACKAGE_ROOT="$(dirname "${PACKAGE_ROOT}")"
done
RESOURCE_DIR="${PACKAGE_ROOT}/tests/resources/nextflow"

readonly workflow="${RESOURCE_DIR}/file_input.nf"
readonly workflow_params='{
  "input_file": "./nf_test_input.txt"
}'
readonly workflow_engine_parameters='{
  "-with-docker": "ubuntu:20.04",
  "-dsl1": ""
}'
readonly input_file="${RESOURCE_DIR}/nf_test_input.txt"

response=$(curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_params=${workflow_params}" \
  -F "workflow_type=NFL" \
  -F "workflow_url=file_input.nf" \
  -F "workflow_engine=nextflow" \
  -F "workflow_engine_parameters=${workflow_engine_parameters}" \
  -F "workflow_attachment=@${workflow}" \
  -F "workflow_attachment=@${input_file}" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs)

if [[ $? -ne 0 ]]; then
  echo -e "Error: Failed to POST runs:\n${response}"
  exit 1
fi

run_id=$(echo "${response}" | jq -r '.run_id')

echo -e "POST /runs is succeeded:\n${response}\n"
echo -e "Please access to the following URL to get the run status:\n"
echo -e "curl -fsSL -X GET http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs/${run_id}\n"
