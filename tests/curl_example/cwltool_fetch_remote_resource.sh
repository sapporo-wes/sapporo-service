#!/usr/bin/env bash
set -euo pipefail

# Define default values for SAPPORO_HOST and SAPPORO_PORT
SAPPORO_HOST=${SAPPORO_HOST:-127.0.0.1}
SAPPORO_PORT=${SAPPORO_PORT:-1122}

readonly workflow_params='{
  "fastq_1": {
    "class": "File",
    "location": "ERR034597_1.small.fq.gz"
  },
  "fastq_2": {
    "class": "File",
    "location": "ERR034597_2.small.fq.gz"
  }
}'
readonly workflow_attachment_obj='[
  {"file_name": "ERR034597_1.small.fq.gz", "file_url": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/ERR034597_1.small.fq.gz"},
  {"file_name": "ERR034597_2.small.fq.gz", "file_url": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/ERR034597_2.small.fq.gz"},
  {"file_name": "trimming_and_qc.cwl", "file_url": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimming_and_qc.cwl"},
  {"file_name": "fastqc.cwl", "file_url": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/fastqc.cwl"},
  {"file_name": "trimmomatic_pe.cwl", "file_url": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimmomatic_pe.cwl"}
]'

response=$(curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_params=${workflow_params}" \
  -F "workflow_type=CWL" \
  -F "workflow_url=trimming_and_qc.cwl" \
  -F "workflow_engine=cwltool" \
  -F "workflow_attachment_obj=${workflow_attachment_obj}" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs)

if [[ $? -ne 0 ]]; then
  echo -e "Error: Failed to POST runs:\n${response}"
  exit 1
fi

run_id=$(echo "${response}" | jq -r '.run_id')

echo -e "POST /runs is succeeded:\n${response}\n"
echo -e "Please access to the following URL to get the run status:\n"
echo -e "curl -fsSL -X GET http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs/${run_id}\n"
