#!/bin/bash
set -eEu

function run_wf() {
  echo "RUNNING" >${state}
  date +"%Y-%m-%dT%H:%M:%S" >${start_time}
  if [[ ${wf_engine_name} == "cwltool" ]]; then
    run_cwltool
    generate_outputs_list
  fi
  date +"%Y-%m-%dT%H:%M:%S" >${end_time}
  echo 0 >${exit_code}
  echo "COMPLETE" >${state}
  exit 0
}

function run_cwltool() {
  local container="commonworkflowlanguage/cwltool:1.0.20191225192155"
  local cmd_txt="${DOCKER_CMD} ${container} --outdir ${outputs_dir} ${wf_engine_params} ${wf_url} ${wf_params} 1>${stdout} 2>${stderr}"
  echo ${cmd_txt} >${cmd}
  eval ${cmd_txt} || executor_error
}

function cancel() {
  # Pre-cancellation procedures
  if [[ ${wf_engine_name} == "cwltool" ]]; then
    cancel_cwltool
  fi
  cancel_by_request
}

function cancel_cwltool() {
  :
}

function generate_outputs_list() {
  python3 -c "from sapporo.util import dump_outputs_list; dump_outputs_list('${run_dir}')"
}

# ==============================================================
# If you are not familiar with sapporo, please don't edit below.

run_dir=$1

# Run dir structure
run_request="${run_dir}/run_request.json"
state="${run_dir}/state.txt"
exe_dir="${run_dir}/exe"
outputs_dir="${run_dir}/outputs"
outputs="${run_dir}/outputs.json"
wf_params="${run_dir}/exe/workflow_params.json"
start_time="${run_dir}/start_time.txt"
end_time="${run_dir}/end_time.txt"
exit_code="${run_dir}/exit_code.txt"
stdout="${run_dir}/stdout.log"
stderr="${run_dir}/stderr.log"
wf_engine_params_file="${run_dir}/workflow_engine_params.txt"
cmd="${run_dir}/cmd.txt"
task_logs="${run_dir}/task.log"

wf_engine_name=$(jq -r ".workflow_engine_name" ${run_request})
wf_url=$(jq -r ".workflow_url" ${run_request})
wf_engine_params=$(head -n 1 ${wf_engine_params_file})

# Sibling docker command
D_SOCK="-v /var/run/docker.sock:/var/run/docker.sock"
D_TMP="-v /tmp:/tmp"
DOCKER_CMD="docker run -i --rm ${D_SOCK} ${D_TMP} -v ${run_dir}:${run_dir} -w=${exe_dir}"

# 4 Exit cases
# 1. The description of run.sh was wrong.
# 2. The workflow_engine terminated in error.
# 3. The system sent a signal to the run.sh, such as SIGHUP.
# 4. The request `POST /runs/${run_id}/cancel` came in.

function desc_error() {
  # exit case 1
  original_exit_code=$?
  echo ${original_exit_code} >${exit_code}
  date +"%Y-%m-%dT%H:%M:%S" >${end_time}
  echo "SYSTEM_ERROR" >${state}
  exit ${original_exit_code}
}

function executor_error() {
  # exit case 2
  original_exit_code=$?
  echo ${original_exit_code} >${exit_code}
  date +"%Y-%m-%dT%H:%M:%S" >${end_time}
  echo "EXECUTOR_ERROR" >${state}
  exit ${original_exit_code}
}

function kill_by_system() {
  # exit case 3
  signal=$1
  if [[ ${signal} == "SIGHUP" ]]; then
    original_exit_code=129
  elif [[ ${signal} == "SIGINT" ]]; then
    original_exit_code=130
  elif [[ ${signal} == "SIGQUIT" ]]; then
    original_exit_code=131
  elif [[ ${signal} == "SIGTERM" ]]; then
    original_exit_code=143
  fi
  echo ${original_exit_code} >${exit_code}
  date +"%Y-%m-%dT%H:%M:%S" >${end_time}
  echo "SYSTEM_ERROR" >${state}
  exit ${original_exit_code}
}

function cancel_by_request() {
  # exit case 4
  original_exit_code=138
  echo ${original_exit_code} >${exit_code}
  date +"%Y-%m-%dT%H:%M:%S" >${end_time}
  echo "CANCELED" >${state}
  exit ${original_exit_code}
}

trap 'desc_error' ERR              # exit case 1
trap 'kill_by_system SIGHUP' HUP   # exit case 3
trap 'kill_by_system SIGINT' INT   # exit case 3
trap 'kill_by_system SIGQUIT' QUIT # exit case 3
trap 'kill_by_system SIGTERM' TERM # exit case 3
trap 'cancel' USR1                 # exit case 4

run_wf
