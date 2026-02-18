#!/usr/bin/env bash

set -euo pipefail

# Main function to run the workflow
function run_wf() {
    check_canceling
    echo "RUNNING" >"${state}"

    # Call the appropriate function based on the workflow engine
    local function_name="run_${wf_engine}"
    if [[ "$(type -t "${function_name}")" == "function" ]]; then
        "${function_name}"
        generate_outputs_list
    else
        executor_error 1
    fi

    upload
    date -u +"%Y-%m-%dT%H:%M:%S" >"${end_time}"
    echo 0 >"${exit_code}"
    echo "COMPLETE" >"${state}"
    generate_ro_crate
    exit 0
}

function _write_and_run() {
    # Write the command to cmd.txt and execute it
    local -n _cmd_ref=$1
    printf '%s ' "${_cmd_ref[@]}" >"${cmd}"
    echo "" >>"${cmd}"
    "${_cmd_ref[@]}" 1>"${stdout}" 2>"${stderr}" || { executor_error $?; }
}

function _append_engine_params() {
    # Append wf_engine_params (word-split) to the given array
    local -n _arr_ref=$1
    if [[ -n "${wf_engine_params}" ]]; then
        local -a extra
        read -ra extra <<< "${wf_engine_params}"
        _arr_ref+=("${extra[@]}")
    fi
}

function run_cwltool() {
    local container="quay.io/commonwl/cwltool:3.1.20260108082145"
    local -a cmd_arr=(docker run --rm
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -e DOCKER_API_VERSION=1.44
        -v /tmp:/tmp
        -v "${run_dir}:${run_dir}"
        "-w=${exe_dir}"
        "${container}"
        --outdir "${outputs_dir}")
    _append_engine_params cmd_arr
    cmd_arr+=("${wf_url}" "${wf_params}")
    _write_and_run cmd_arr
}

function run_nextflow() {
    local container="nextflow/nextflow:25.10.4"
    local -a cmd_arr=(docker run --rm
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -v "${run_dir}:${run_dir}"
        "-w=${exe_dir}"
        "${container}"
        nextflow run "${wf_url}")
    _append_engine_params cmd_arr
    cmd_arr+=(-params-file "${wf_params}" --outdir "${outputs_dir}" -work-dir "${exe_dir}")
    _write_and_run cmd_arr
}

function run_toil() {
    local container="quay.io/ucsc_cgl/toil:9.1.1"
    local -a cmd_arr=(docker run --rm
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -e DOCKER_API_VERSION=1.44
        -v "${run_dir}:${run_dir}"
        "-w=${exe_dir}"
        -e "TOIL_WORKDIR=${exe_dir}"
        "${container}"
        toil-cwl-runner --outdir "${outputs_dir}")
    _append_engine_params cmd_arr
    cmd_arr+=("${wf_url}" "${wf_params}")
    _write_and_run cmd_arr
}

function run_cromwell() {
    local container="ghcr.io/sapporo-wes/cromwell-with-docker:92"
    local -a cmd_arr=(docker run --rm
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -v /tmp:/tmp
        -v "${run_dir}:${run_dir}"
        "-w=${exe_dir}"
        "${container}"
        run)
    _append_engine_params cmd_arr
    cmd_arr+=("${wf_url}" -i "${wf_params}" -m "${exe_dir}/metadata.json")
    _write_and_run cmd_arr

    # Copy WDL outputs from Cromwell metadata
    if [[ ! -f "${exe_dir}/metadata.json" ]]; then
        echo "Warning: metadata.json not found" >>"${stderr}"
    else
        while read -r output_file; do
            if [[ -n "${output_file}" && -f "${output_file}" ]]; then
                cp "${output_file}" "${outputs_dir}/" || true
            fi
        done < <(jq -r '.outputs | to_entries[] | .value // empty' "${exe_dir}/metadata.json" 2>>"${stderr}")
    fi
}

function run_snakemake() {
    local wf_url_local
    if [[ "${wf_url}" == http://* ]] || [[ "${wf_url}" == https://* ]]; then
        wf_url_local="${exe_dir}/$(basename "${wf_url}")"
        curl -fsSL -o "${wf_url_local}" "${wf_url}" || { executor_error $?; }
    elif [[ "${wf_url}" == /* ]]; then
        wf_url_local="${wf_url}"
    else
        wf_url_local="${exe_dir}/${wf_url}"
    fi

    local container="snakemake/snakemake:v9.16.3"
    local -a cmd_arr=(docker run --rm
        -v "${run_dir}:${run_dir}"
        "-w=${exe_dir}"
        "${container}"
        bash -c)
    # Build the inner shell command as a single string for bash -c
    local -a smk_parts=(snakemake)
    _append_engine_params smk_parts
    smk_parts+=(--configfile "${wf_params}" --snakefile "${wf_url_local}")
    local smk_run
    smk_run=$(printf '%q ' "${smk_parts[@]}")
    local inner_cmd="${smk_run} && snakemake --configfile ${wf_params} --snakefile ${wf_url_local} --summary 2>/dev/null | tail -n +2 | cut -f 1 > ${exe_dir}/.snakemake_outputs"
    cmd_arr+=("${inner_cmd}")
    _write_and_run cmd_arr

    while read -r file_path; do
        local dir_path
        dir_path=$(dirname "${file_path}")
        mkdir -p "${outputs_dir}/${dir_path}"
        cp "${exe_dir}/${file_path}" "${outputs_dir}/${file_path}" 2>/dev/null || true
    done < "${exe_dir}/.snakemake_outputs"
    rm -f "${exe_dir}/.snakemake_outputs"
}

function run_ep3() {
    local container="ghcr.io/tom-tan/ep3:v1.7.0"
    local -a cmd_arr=(docker run --rm
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -e DOCKER_API_VERSION=1.44
        -v /tmp:/tmp
        -v "${run_dir}:${run_dir}"
        "-w=${exe_dir}"
        "${container}"
        ep3-runner --verbose --outdir "${outputs_dir}")
    _append_engine_params cmd_arr
    cmd_arr+=("${wf_url}" "${wf_params}")
    _write_and_run cmd_arr
}

function run_streamflow() {
    # StreamFlow's DockerConnector requires the docker CLI binary.
    # In a DinD setup the dev-container's /usr/local/bin/docker is NOT on the
    # host filesystem, so we copy it into exe_dir (which IS host-mounted) and
    # bind-mount it into the StreamFlow container.
    local docker_stage="${exe_dir}/.docker-bin"
    cp "$(command -v docker)" "${docker_stage}"
    local container="alphaunito/streamflow:0.2.0.dev14"
    local -a cmd_arr=(docker run --rm
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -v "${docker_stage}:/usr/bin/docker:ro"
        -v /tmp:/tmp
        -v "${run_dir}:${run_dir}"
        "-w=${exe_dir}"
        "${container}"
        cwl-runner --outdir "${outputs_dir}")
    _append_engine_params cmd_arr
    cmd_arr+=("${wf_url}" "${wf_params}")
    _write_and_run cmd_arr
}

function cancel() {
    # Edit this function for environment-specific cancellation procedures
    if [[ "${wf_engine}" == "cwltool" ]]; then
        cancel_cwltool
    fi
    cancel_by_request
}

function cancel_cwltool() {
    # Add specific cancellation procedures for cwltool if needed
    :
}

function upload() {
    # Edit this function for environment-specific upload procedures
    :
}

# ==============================================================
# If you are not familiar with sapporo, please don't edit below.

# Get the run directory from the first argument
run_dir=$1

# Define the run directory structure
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
system_logs="${run_dir}/system_logs.json"
ro_crate="${run_dir}/ro-crate-metadata.json"

# Extract workflow engine and URL from the run request
wf_engine=$(jq -r ".workflow_engine" "${run_request}")
wf_url=$(jq -r ".workflow_url" "${run_request}")
wf_engine_params=$(head -n 1 "${wf_engine_params_file}")

# Docker command settings are now defined per-engine in each run_* function

function generate_outputs_list() {
    sapporo-cli dump-outputs "${run_dir}" || { executor_error $?; }
}

function generate_ro_crate() {
    sapporo-cli generate-ro-crate "${run_dir}" 2>>"${stderr}" \
        || echo '{"@error": "RO-Crate generation failed. Check stderr.log for details."}' >"${ro_crate}"
    # If you want to upload ro-crate-metadata.json, write the process here.
}

function desc_error() {
    local original_exit_code=1
    echo "${original_exit_code}" >"${exit_code}"
    date -u +"%Y-%m-%dT%H:%M:%S" >"${end_time}"
    echo "SYSTEM_ERROR" >"${state}"
    exit "${original_exit_code}"
}

function executor_error() {
    local original_exit_code=${1:-1}
    echo "${original_exit_code}" >"${exit_code}"
    date -u +"%Y-%m-%dT%H:%M:%S" >"${end_time}"
    echo "EXECUTOR_ERROR" >"${state}"
    generate_ro_crate
    exit "${original_exit_code}"
}

function kill_by_system() {
    local signal=$1
    local original_exit_code
    case "${signal}" in
    "SIGHUP") original_exit_code=129 ;;
    "SIGINT") original_exit_code=130 ;;
    "SIGQUIT") original_exit_code=131 ;;
    "SIGTERM") original_exit_code=143 ;;
    *) original_exit_code=1 ;;
    esac
    echo "${original_exit_code}" >"${exit_code}"
    date -u +"%Y-%m-%dT%H:%M:%S" >"${end_time}"
    echo "SYSTEM_ERROR" >"${state}"
    exit "${original_exit_code}"
}

function cancel_by_request() {
    # Requested POST /runs/${run_id}/cancel
    local original_exit_code=138
    echo "${original_exit_code}" >"${exit_code}"
    date -u +"%Y-%m-%dT%H:%M:%S" >"${end_time}"
    echo "CANCELED" >"${state}"
    exit "${original_exit_code}"
}

function check_canceling() {
    local state_content
    state_content=$(cat "${state}")
    if [[ "${state_content}" == "CANCELING" ]]; then
        cancel
    fi
}

trap 'desc_error' ERR
trap 'kill_by_system SIGHUP' HUP
trap 'kill_by_system SIGINT' INT
trap 'kill_by_system SIGQUIT' QUIT
trap 'kill_by_system SIGTERM' TERM
trap 'cancel' USR1 # Handle cancellation request

# Run as a background process to handle cancellation requests
run_wf &
bg_pid=$!
wait $bg_pid || true
