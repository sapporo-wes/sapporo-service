#!/usr/bin/env bash
set -Eeu

SCRIPT_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) &>/dev/null && pwd -P)
RESOURCE_DIR="${SCRIPT_DIR}/../../../../resources/snakemake"

workflow_engine_parameters="${SCRIPT_DIR}/workflow_engine_parameters.json"

script_1="${RESOURCE_DIR}/scripts/plot-quals.py"
env_1="${RESOURCE_DIR}/envs/stats.yaml"
env_2="${RESOURCE_DIR}/envs/calling.yaml"
env_3="${RESOURCE_DIR}/envs/mapping.yaml"
sample_1="${RESOURCE_DIR}/data/samples/A.fastq"
sample_2="${RESOURCE_DIR}/data/samples/B.fastq"
sample_3="${RESOURCE_DIR}/data/samples/C.fastq"
sample_4="${RESOURCE_DIR}/data/genome.fa"
sample_5="${RESOURCE_DIR}/data/genome.fa.amb"
sample_6="${RESOURCE_DIR}/data/genome.fa.fai"
sample_7="${RESOURCE_DIR}/data/genome.fa.sa"
sample_8="${RESOURCE_DIR}/data/genome.fa.pac"
sample_9="${RESOURCE_DIR}/data/genome.fa.ann"
sample_10="${RESOURCE_DIR}/data/genome.fa.bwt"

curl -fsSL -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "workflow_params={}" \
  -F "workflow_type=SMK" \
  -F "workflow_type_version=1.0" \
  -F "workflow_url=https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/snakemake/Snakefile" \
  -F "workflow_engine_name=snakemake" \
  -F "workflow_engine_parameters=<${workflow_engine_parameters}" \
  -F "workflow_attachment=@${script_1};filename=scripts/plot-quals.py" \
  -F "workflow_attachment=@${env_1};filename=envs/stats.yaml" \
  -F "workflow_attachment=@${env_2};filename=envs/calling.yaml" \
  -F "workflow_attachment=@${env_3};filename=envs/mapping.yaml" \
  -F "workflow_attachment=@${sample_1};filename=data/samples/A.fastq" \
  -F "workflow_attachment=@${sample_2};filename=data/samples/B.fastq" \
  -F "workflow_attachment=@${sample_3};filename=data/samples/C.fastq" \
  -F "workflow_attachment=@${sample_4};filename=data/genome.fa" \
  -F "workflow_attachment=@${sample_5};filename=data/genome.fa.amb" \
  -F "workflow_attachment=@${sample_6};filename=data/genome.fa.fai" \
  -F "workflow_attachment=@${sample_7};filename=data/genome.fa.sa" \
  -F "workflow_attachment=@${sample_8};filename=data/genome.fa.pac" \
  -F "workflow_attachment=@${sample_9};filename=data/genome.fa.ann" \
  -F "workflow_attachment=@${sample_10};filename=data/genome.fa.bwt" \
  http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs
