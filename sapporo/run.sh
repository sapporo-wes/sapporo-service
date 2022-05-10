#!/usr/bin/env bash
set -eu

function run_wf() {
  echo "INITIALIZING" >${state}
  download_workflow_attachment
  echo "RUNNING" >${state}
  date +"%Y-%m-%dT%H:%M:%S" >${start_time}
  # e.g. when wf_engine_name=cwltool, call function run_cwltool
  local function_name="run_${wf_engine_name}"
  if [[ "$(type -t ${function_name})" == "function" ]]; then
    ${function_name}
    generate_outputs_list
  else
    executor_error
  fi
  upload
  date +"%Y-%m-%dT%H:%M:%S" >${end_time}
  echo 0 >${exit_code}
  echo "COMPLETE" >${state}
  exit 0
}

function run_cwltool() {
  local container="quay.io/commonwl/cwltool:3.1.20211107152837"
  local cmd_txt="${DOCKER_CMD} ${container} --outdir ${outputs_dir} ${wf_engine_params} ${wf_url} ${wf_params} 1>${stdout} 2>${stderr}"
  echo ${cmd_txt} >${cmd}
  eval ${cmd_txt} || executor_error
}

function run_nextflow() {
  local container="nextflow/nextflow:21.10.5"
  local cmd_txt=""
  if [[ $(jq 'select(.outdir) != null' ${wf_params}) ]]; then
    # It has outdir as params.
    cmd_txt="docker run -i --rm ${D_SOCK} -v ${run_dir}:${run_dir} -w=${exe_dir} ${container} nextflow -dockerize run ${wf_url} ${wf_engine_params} -params-file ${wf_params} --outdir ${outputs_dir} 1>${stdout} 2>${stderr}"
  else
    # It has NOT outdir as params.
    cmd_txt="docker run -i --rm ${D_SOCK} -v ${run_dir}:${run_dir} -w=${exe_dir} ${container} nextflow -dockerize run ${wf_url} ${wf_engine_params} -params-file ${wf_params} -work-dir ${outputs_dir} 1>${stdout} 2>${stderr}"
  fi
  find ${exe_dir} -type f -exec chmod 777 {} \;
  echo ${cmd_txt} >${cmd}
  eval ${cmd_txt} || executor_error
}

function run_toil() {
  local container="quay.io/ucsc_cgl/toil:4.1.0"
  local cmd_txt="${DOCKER_CMD} -e TOIL_WORKDIR=${exe_dir} ${container} toil-cwl-runner ${wf_engine_params} ${wf_url} ${wf_params} 1>${stdout} 2>${stderr}"
  echo ${cmd_txt} >${cmd}
  eval ${cmd_txt} || executor_error
}

function run_cromwell() {
  local container="broadinstitute/cromwell:72"
  local wf_type=$(jq -r ".workflow_type" ${run_request})
  local wf_type_version=$(jq -r ".workflow_type_version" ${run_request})
  local cmd_txt="docker run -i --rm ${D_SOCK} -v ${run_dir}:${run_dir} -v /tmp:/tmp -v /usr/bin/docker:/usr/bin/docker -w=${exe_dir} ${container} run ${wf_engine_params} ${wf_url} -i ${wf_params} -m ${exe_dir}/metadata.json --type ${wf_type} --type-version ${wf_type_version} 1>${stdout} 2>${stderr}"
  echo ${cmd_txt} >${cmd}
  eval ${cmd_txt} || executor_error
  if [[ ${wf_type} == "CWL" ]]; then
    jq -r ".outputs[].location" "${exe_dir}/metadata.json" | while read output_file; do
      cp ${output_file} ${outputs_dir}/ || true
    done
  elif [[ ${wf_type} == "WDL" ]]; then
    jq -r ".outputs | to_entries[] | .value" "${exe_dir}/metadata.json" | while read output_file; do
      cp ${output_file} ${outputs_dir}/ || true
    done
  fi
}

function run_snakemake() {
  if [[ "${wf_url}" == http://* ]] || [[ "${wf_url}" == https://* ]]; then
    # It is a remote file.
    local wf_url_local="${exe_dir}/$(basename ${wf_url})"
    curl -fsSL -o ${wf_url_local} ${wf_url} || executor_error
  else
    # It is a local file.
    if [[ "${wf_url}" == /* ]]; then
      local wf_url_local="${wf_url}"
    else
      local wf_url_local="${exe_dir}/${wf_url}"
    fi
  fi
  local wf_basedir="$(dirname ${wf_url_local})"
  # NOTE these are common conventions but not hard requirements for Snakemake Standardized Usage.
  local wf_schemas_dir="${wf_basedir}/schemas"
  local wf_scripts_dir="${wf_basedir}/scripts"
  local wf_results_dir="${wf_basedir}/results"
  if [[ -d "${wf_scripts_dir}" ]]; then
    # directory is local (not an URL) and it exists
    chmod a+x "${wf_scripts_dir}/"*
  fi

  local container="snakemake/snakemake:v6.9.1"
  local cmd_txt="docker run -i --rm -v ${run_dir}:${run_dir} -w=${exe_dir} ${container} snakemake ${wf_engine_params} --configfile ${wf_params} --snakefile ${wf_url_local} 1>${stdout} 2>${stderr}"
  echo ${cmd_txt} >${cmd}
  eval ${cmd_txt} || executor_error

  docker run -i --rm -v ${run_dir}:${run_dir} -w=${exe_dir} ${container} \
    snakemake --configfile ${wf_params} --snakefile ${wf_url_local} --summary 2>/dev/null | tail -n +2 | cut -f 1 |
    while read file_path; do
      dir_path=$(dirname ${file_path})
      mkdir -p "${outputs_dir}/${dir_path}"
      cp "${exe_dir}/${file_path}" "${outputs_dir}/${file_path}" 2>/dev/null || true
    done
}

function run_ep3() {
  local container="ghcr.io/tom-tan/ep3:v1.7.0"
  local cmd_txt="${DOCKER_CMD} ${container} ep3-runner --verbose --outdir ${outputs_dir} ${wf_engine_params} ${wf_url} ${wf_params} 1>${stdout} 2>${stderr}"
  echo ${cmd_txt} >${cmd}
  eval ${cmd_txt} || executor_error
}

function run_streamflow() {
  if [[ "${wf_url}" == http://* ]] || [[ "${wf_url}" == https://* ]]; then
    # It is a remote file.
    local wf_url_local="${exe_dir}/$(basename ${wf_url})"
    curl -fsSL -o ${wf_url_local} ${wf_url} || executor_error
  else
    # It is a local file.
    if [[ "${wf_url}" == /* ]]; then
      local wf_url_local="${wf_url}"
    else
      local wf_url_local="${exe_dir}/${wf_url}"
    fi
  fi
  local container="alphaunito/streamflow:0.1.3-base"
  local cmd_txt="docker run --mount type=bind,source=${run_dir},target=/streamflow/project --mount type=bind,source=${outputs_dir},target=/streamflow/results ${container} run /streamflow/project/exe/$(basename ${wf_url_local}) 1>${stdout} 2>${stderr}"
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

function download_workflow_attachment() {
  python3 -c "from sapporo.run import download_workflow_attachment; download_workflow_attachment('${run_dir}')" || executor_error
}

function generate_outputs_list() {
  python3 -c "from sapporo.run import dump_outputs_list; dump_outputs_list('${run_dir}')" || executor_error
}

function upload() {
  local protocol=$(jq -r '.tags | fromjson | .export_output.protocol' ${run_request})
  case ${protocol} in
  's3')
    upload_to_s3
    ;;
  esac
}

function upload_to_s3() {
  local container="amazon/aws-cli:2.0.45"

  local endpoint=$(jq -r '.tags | fromjson | .export_output.endpoint' ${run_request})
  local access_key=$(jq -r '.tags | fromjson | .export_output.access_key' ${run_request})
  local secret_access_key=$(jq -r '.tags | fromjson | .export_output.secret_access_key' ${run_request})
  local bucket_name=$(jq -r '.tags | fromjson | .export_output.bucket_name' ${run_request})
  local dirname=$(jq -r '.tags | fromjson | .export_output.dirname' ${run_request})

  local export_script="${run_dir}/upload_to_s3.sh"
  printf "\
aws configure set aws_access_key_id ${access_key}; \
aws configure set aws_secret_access_key ${secret_access_key}; \
aws configure set default.region us-west-2; \
aws configure set default.s3.signature_version s3v4; \
aws --endpoint-url ${endpoint} s3api head-bucket --bucket ${bucket_name} || aws --endpoint-url ${endpoint} s3 mb s3://${bucket_name}; \
aws --endpoint-url ${endpoint} s3 cp ${outputs_dir} s3://${bucket_name}/${dirname} --recursive
" >>${export_script}

  local up_stdout="${run_dir}/upload.stdout.log"
  local up_stderr="${run_dir}/upload.stderr.log"

  local cmd_txt="${DOCKER_CMD} --network sapporo-network --entrypoint=/bin/bash -v ${export_script}:/export.sh ${container} /export.sh 1>>${up_stdout} 2>>${up_stderr}"

  echo ${cmd_txt} >>${up_stdout}
  eval ${cmd_txt} || uploader_error
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

# Meta characters are escaped.
wf_engine_name=$(jq -r ".workflow_engine_name" ${run_request})
wf_url=$(jq -r ".workflow_url" ${run_request})
wf_engine_params=$(head -n 1 ${wf_engine_params_file})

# Sibling docker command
D_SOCK="-v /var/run/docker.sock:/var/run/docker.sock"
D_TMP="-v /tmp:/tmp"
DOCKER_CMD="docker run -i --rm ${D_SOCK} -e DOCKER_HOST=unix:///var/run/docker.sock ${D_TMP} -v ${run_dir}:${run_dir} -w=${exe_dir}"

# 4 Exit cases
# 1. The description of run.sh was wrong.
# 2. The workflow_engine terminated in error.
# 3. The system sent a signal to the run.sh, such as SIGHUP.
# 4. The request `POST /runs/${run_id}/cancel` came in.

function desc_error() {
  # Exit case 1: The description of run.sh was wrong.
  original_exit_code=$?
  echo ${original_exit_code} >${exit_code}
  date +"%Y-%m-%dT%H:%M:%S" >${end_time}
  echo "SYSTEM_ERROR" >${state}
  exit ${original_exit_code}
}

function executor_error() {
  # Exit case 2: The workflow_engine terminated in error.
  original_exit_code=$?
  echo ${original_exit_code} >${exit_code}
  date +"%Y-%m-%dT%H:%M:%S" >${end_time}
  echo "EXECUTOR_ERROR" >${state}
  exit ${original_exit_code}
}

function uploader_error() {
  # Exit case 2.1: Upload function terminated in error.
  original_exit_code=$?
  echo ${original_exit_code} >${exit_code}
  date +"%Y-%m-%dT%H:%M:%S" >${end_time}
  echo "UPLOADER_ERROR" >${state}
  exit ${original_exit_code}
}

function kill_by_system() {
  # Exit case 3: The system sent a signal to the run.sh, such as SIGHUP.
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
  # Exit case 4: The request `POST /runs/${run_id}/cancel` came in.
  original_exit_code=138
  echo ${original_exit_code} >${exit_code}
  date +"%Y-%m-%dT%H:%M:%S" >${end_time}
  echo "CANCELED" >${state}
  exit ${original_exit_code}
}

trap 'desc_error' ERR              # Exit case 1
trap 'kill_by_system SIGHUP' HUP   # Exit case 3
trap 'kill_by_system SIGINT' INT   # Exit case 3
trap 'kill_by_system SIGQUIT' QUIT # Exit case 3
trap 'kill_by_system SIGTERM' TERM # Exit case 3
trap 'cancel' USR1                 # Exit case 4

run_wf
