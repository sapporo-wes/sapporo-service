#!/usr/bin/env bash
set -euo pipefail

# Define default values for SAPPORO_HOST and SAPPORO_PORT
SAPPORO_HOST=${SAPPORO_HOST:-127.0.0.1}
SAPPORO_PORT=${SAPPORO_PORT:-1122}

readonly workflow_params='{
  "fastq_1": {
    "class": "File",
    "location": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/ERR034597_1.small.fq.gz"
  },
  "fastq_2": {
    "class": "File",
    "location": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/ERR034597_2.small.fq.gz"
  }
}'

response=$(curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_params=${workflow_params}" \
  -F "workflow_type=CWL" \
  -F "workflow_type_version=v1.0" \
  -F "workflow_url=https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimming_and_qc_remote.cwl" \
  -F "workflow_engine_name=cwltool" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs)

if [[ $? -ne 0 ]]; then
  echo -e "Error: Failed to POST runs:\n${response}"
  exit 1
fi

run_id=$(echo "${response}" | jq -r '.run_id')

echo -e "POST /runs is succeeded:\n${response}\n"
echo -e "Please access to the following URL to get the run status:\n"
echo -e "curl -fsSL -X GET http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs/${run_id}\n"
