#!/bin/bash

function run_wf() {
  if [[ ${execution_engine} == "cwltool" ]]; then
    run_cwltool
  elif [[ ${execution_engine} == "nextflow" ]]; then
    run_nextflow
  elif [[ ${execution_engine} == "toil" ]]; then
    run_toil
  fi
}

function run_cwltool() {
  echo "RUNNING" >$status
  cwltool --custom-net=sapporo-network --outdir $run_dir $workflow $workflow_parameters 1>$stdout 2>$stderr || echo "EXECUTOR_ERROR" >$status
  echo "COMPLETE" >$status
  exit 0
}

function run_nextflow() {
  :
}

function run_toil() {
  :
}

function cancel() {
  if [[ ${execution_engine} == "cwltool" ]]; then
    cancel_cwltool
  elif [[ ${execution_engine} == "nextflow" ]]; then
    cancel_nextflow
  elif [[ ${execution_engine} == "toil" ]]; then
    cancel_toil
  fi
}

function cancel_cwltool() {
  exit 0
}

function cancel_nextflow() {
  :
}

function cancel_toil() {
  :
}

# =============

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
RUN_BASE_DIR=$(cd ${SCRIPT_DIR}/.. && pwd)
uuid=$1
run_dir=$RUN_BASE_DIR/run/$(echo ${uuid} | cut -c 1-2)/${uuid}
cd $run_dir
output_dir="${run_dir}/output"
run_order="${run_dir}/run_order.yml"
workflow="${run_dir}/workflow"
workflow_parameters="${run_dir}/workflow_parameters"
status="${run_dir}/status.txt"
pid_info="${run_dir}/run.pid"
upload_url="${run_dir}/upload_url.txt"
stdout="${run_dir}/stdout.log"
stderr="${run_dir}/stderr.log"
execution_engine=$(cat ${run_order} | yq -r '.execution_engine_name')

trap 'echo "SYSTEM_ERROR" > ${status_file}' 1 2 3 15
trap 'cancel' 10

run_wf
