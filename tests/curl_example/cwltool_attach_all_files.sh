#!/usr/bin/env bash
set -euo pipefail

# Define default values for SAPPORO_HOST and SAPPORO_PORT
SAPPORO_HOST=${SAPPORO_HOST:-127.0.0.1}
SAPPORO_PORT=${SAPPORO_PORT:-1122}

PACKAGE_ROOT="$(cd "$(dirname "$0")" && pwd)"
while [[ "${PACKAGE_ROOT}" != "/" && ! -f "${PACKAGE_ROOT}/setup.py" ]]; do
  PACKAGE_ROOT="$(dirname "${PACKAGE_ROOT}")"
done
RESOURCE_DIR="${PACKAGE_ROOT}/tests/resources/cwltool"

readonly workflow="${RESOURCE_DIR}/trimming_and_qc.cwl"
readonly workflow_params='{
  "fastq_1": {
    "class": "File",
    "path": "ERR034597_1.small.fq.gz"
  },
  "fastq_2": {
    "class": "File",
    "path": "ERR034597_2.small.fq.gz"
  }
}'
readonly fastq_1="${RESOURCE_DIR}/ERR034597_1.small.fq.gz"
readonly fastq_2="${RESOURCE_DIR}/ERR034597_2.small.fq.gz"
readonly tool_1="${RESOURCE_DIR}/fastqc.cwl"
readonly tool_2="${RESOURCE_DIR}/trimmomatic_pe.cwl"

response=$(curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_params=${workflow_params}" \
  -F "workflow_type=CWL" \
  -F "workflow_type_version=v1.0" \
  -F "workflow_url=./trimming_and_qc.cwl" \
  -F "workflow_engine=cwltool" \
  -F "workflow_attachment=@${workflow}" \
  -F "workflow_attachment=@${tool_1}" \
  -F "workflow_attachment=@${tool_2}" \
  -F "workflow_attachment=@${fastq_1}" \
  -F "workflow_attachment=@${fastq_2}" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs)

if [[ $? -ne 0 ]]; then
  echo -e "Error: Failed to POST runs:\n${response}"
  exit 1
fi

run_id=$(echo "${response}" | jq -r '.run_id')

echo -e "POST /runs is succeeded:\n${response}\n"
echo -e "Please access to the following URL to get the run status:\n"
echo -e "curl -fsSL -X GET http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs/${run_id}\n"
