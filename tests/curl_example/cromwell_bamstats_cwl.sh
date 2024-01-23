#!/usr/bin/env bash
set -euo pipefail

# Define default values for SAPPORO_HOST and SAPPORO_PORT
SAPPORO_HOST=${SAPPORO_HOST:-127.0.0.1}
SAPPORO_PORT=${SAPPORO_PORT:-1122}

PACKAGE_ROOT="$(cd "$(dirname "$0")" && pwd)"
while [[ "${PACKAGE_ROOT}" != "/" && ! -f "${PACKAGE_ROOT}/setup.py" ]]; do
  PACKAGE_ROOT="$(dirname "${PACKAGE_ROOT}")"
done
RESOURCE_DIR="${PACKAGE_ROOT}/tests/resources/cromwell/dockstore-tool-bamstats"

readonly workflow="${RESOURCE_DIR}/Dockstore.cwl"
readonly workflow_params="${RESOURCE_DIR}/test.json"
readonly data="${RESOURCE_DIR}/tiny.bam"
readonly tags='{
  "workflow_name": "dockstore-tool-bamstats-cwl"
}'

response=$(curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_params=<${workflow_params}" \
  -F "workflow_type=CWL" \
  -F "workflow_type_version=v1.0" \
  -F "workflow_url=./Dockstore.cwl" \
  -F "workflow_engine_name=cromwell" \
  -F "tags=${tags}" \
  -F "workflow_attachment=@${workflow}" \
  -F "workflow_attachment=@${data}" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs)

if [[ $? -ne 0 ]]; then
  echo -e "Error: Failed to POST runs:\n${response}"
  exit 1
fi

run_id=$(echo "${response}" | jq -r '.run_id')

echo -e "POST /runs is succeeded:\n${response}\n"
echo -e "Please access to the following URL to get the run status:\n"
echo -e "curl -fsSL -X GET http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs/${run_id}\n"
