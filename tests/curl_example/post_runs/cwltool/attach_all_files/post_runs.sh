#!/usr/bin/env bash
set -Eeu

SCRIPT_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) &>/dev/null && pwd -P)

workflow_params="${SCRIPT_DIR}/workflow_params.json"
fastq_1="${SCRIPT_DIR}/../../../../resources/cwltool/ERR034597_1.small.fq.gz"
fastq_2="${SCRIPT_DIR}/../../../../resources/cwltool/ERR034597_2.small.fq.gz"
workflow="${SCRIPT_DIR}/../../../../resources/cwltool/trimming_and_qc.cwl"
tool_1="${SCRIPT_DIR}/../../../../resources/cwltool/fastqc.cwl"
tool_2="${SCRIPT_DIR}/../../../../resources/cwltool/trimmomatic_pe.cwl"

curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_params=<${workflow_params}" \
  -F "workflow_type=CWL" \
  -F "workflow_type_version=v1.0" \
  -F "workflow_url=./trimming_and_qc.cwl" \
  -F "workflow_engine_name=cwltool" \
  -F "workflow_attachment=@${fastq_1}" \
  -F "workflow_attachment=@${fastq_2}" \
  -F "workflow_attachment=@${workflow}" \
  -F "workflow_attachment=@${tool_1}" \
  -F "workflow_attachment=@${tool_2}" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs
