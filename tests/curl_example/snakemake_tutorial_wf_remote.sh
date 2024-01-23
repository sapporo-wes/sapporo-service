#!/usr/bin/env bash
set -euo pipefail

# Define default values for SAPPORO_HOST and SAPPORO_PORT
SAPPORO_HOST=${SAPPORO_HOST:-127.0.0.1}
SAPPORO_PORT=${SAPPORO_PORT:-1122}

PACKAGE_ROOT="$(cd "$(dirname "$0")" && pwd)"
while [[ "${PACKAGE_ROOT}" != "/" && ! -f "${PACKAGE_ROOT}/setup.py" ]]; do
  PACKAGE_ROOT="$(dirname "${PACKAGE_ROOT}")"
done
RESOURCE_DIR="${PACKAGE_ROOT}/tests/resources/snakemake"

readonly workflow_engine_parameters='{
  "--cores": "1",
  "--use-conda": ""
}'

get_file_path_and_name() {
  local file_path="$1"
  local relative_path="${file_path#${RESOURCE_DIR}/}"
  echo "@${file_path};filename=${relative_path}"
}

generate_workflow_attachment() {
  local dir="$1"
  local workflow_attachment=""
  for file_path in $(find "${dir}" -type f); do
    workflow_attachment="${workflow_attachment} -F workflow_attachment=$(get_file_path_and_name "${file_path}")"
  done
  echo "${workflow_attachment}"
}

workflow_attachment="$(generate_workflow_attachment "${RESOURCE_DIR}")"

response=$(curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_params={}" \
  -F "workflow_type=SMK" \
  -F "workflow_type_version=1.0" \
  -F "workflow_url=https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/snakemake/Snakefile" \
  -F "workflow_engine_name=snakemake" \
  -F "workflow_engine_parameters=${workflow_engine_parameters}" \
  ${workflow_attachment} \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs)

if [[ $? -ne 0 ]]; then
  echo -e "Error: Failed to POST runs:\n${response}"
  exit 1
fi

run_id=$(echo "${response}" | jq -r '.run_id')

echo -e "POST /runs is succeeded:\n${response}\n"
echo -e "Please access to the following URL to get the run status:\n"
echo -e "curl -fsSL -X GET http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs/${run_id}\n"
