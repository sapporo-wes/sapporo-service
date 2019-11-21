#!/bin/bash
set -eEx

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
  echo "RUNNING" >${status}
  local container="commonworkflowlanguage/cwltool:1.0.20191022103248"
  ${DOCKER_CMD} ${container} --custom-net=sapporo-network --outdir /work/output workflow workflow_parameters 1>${stdout} 2>${stderr}
  if [[ "${upload_protocol_name}" == "s3" ]]; then
    s3_upload
  fi
  echo "COMPLETE" >${status}
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
  exit 1
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
cd ${run_dir}

# Files provided in run dir
run_order="${run_dir}/run_order.yml"
execution_engine=$(cat ${run_order} | yq -r '.execution_engine_name')
workflow="${run_dir}/workflow"
workflow_parameters="${run_dir}/workflow_parameters"
upload_info="${run_dir}/upload_info"
upload_protocol_name=$(cat ${upload_info} | yq -r .protocol_name)
pid_info="${run_dir}/run.pid"

# Files that becomes the API response
output_dir="${run_dir}/output"
status="${run_dir}/status.txt"
stdout="${run_dir}/stdout.log"
stderr="${run_dir}/stderr.log"
upload_url="${run_dir}/upload_url.txt"

# Sibling docker command
D_LIB="-v /var/lib/docker:/var/lib/docker"
D_NETWORK_OPT="--network=sapporo-network"
D_SOCK="-v /var/run/docker.sock:/var/run/docker.sock"
D_TMP="-v /tmp:/tmp"
DOCKER_CMD="docker run -i --rm ${D_NETWORK_OPT} ${D_SOCK} ${D_LIB} ${D_TMP} -v ${run_dir}:/work -w=/work"

function s3_upload() {
  local endpoint=$(cat ${upload_info} | yq -r .parameters.endpoint)
  local access_key=$(cat ${upload_info} | yq -r .parameters.access_key)
  local secret_access_key=$(cat ${upload_info} | yq -r .parameters.secret_access_key)
  local bucket=$(cat ${upload_info} | yq -r .parameters.bucket)
  local upload_dir=$(cat ${upload_info} | yq -r .parameters.upload_dir)
  export AWS_ACCESS_KEY_ID=${access_key}
  export AWS_SECRET_ACCESS_KEY=${secret_access_key}
  aws --endpoint="http://${endpoint}" s3 cp --recursive ${output_dir} "s3://${bucket}/${upload_dir}/" || eval 'echo "EXECUTOR_ERROR" >$status; exit 1'
  printf "http://${endpoint}/${bucket}/${upload_dir}" >${upload_url}
}

trap 'echo "SYSTEM_ERROR" >${status}; exit 1' 1 2 3 15
trap 'cancel' 10
trap 'echo "EXECUTOR_ERROR" >${status}; exit 1' ERR

run_wf
