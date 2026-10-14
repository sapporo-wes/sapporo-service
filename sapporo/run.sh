#!/usr/bin/env bash

set -Eeuo pipefail
# Job control gives run_wf its own process group, so that cancel can stop the engine and
# everything it started with one signal to the group.
set -m

# Main function to run the workflow
function run_wf() {
    check_canceling
    _write_control_file "${state}" "RUNNING"
    set_extra_docker_args
    # cwltool, cromwell, ep3 and streamflow keep their temporary files here instead of in the host /tmp,
    # so that runs do not see each other's files and the files are deleted with the run
    mkdir -p "${tmp_dir}"
    chmod 0775 "${tmp_dir}"

    # Call the appropriate function based on the workflow engine
    local function_name="run_${wf_engine}"
    if [[ "$(type -t "${function_name}")" == "function" ]]; then
        "${function_name}"
        generate_outputs_list
    else
        executor_error 1
    fi

    upload
    # A signal handler in the parent process may have taken over the outcome while the engine ran
    _owns_outcome || exit 0
    _write_outcome 0 "COMPLETE"
    generate_ro_crate
    exit 0
}

function _write_and_run() {
    # Write the command to cmd.txt and execute it
    local -n _cmd_ref=$1
    rm -f "${engine_cid}"
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
    local container="quay.io/commonwl/cwltool:3.3.20260925135507"
    local -a cmd_arr=(docker run --rm --cidfile "${engine_cid}"
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -e DOCKER_API_VERSION=1.44
        -v "${exe_dir}:${exe_dir}"
        -v "${outputs_dir}:${outputs_dir}"
        -v "${tmp_dir}:${tmp_dir}"
        -e "TMPDIR=${tmp_dir}"
        "${extra_docker_args[@]+"${extra_docker_args[@]}"}"
        "-w=${exe_dir}"
        # The image's entrypoint script runs cwltool as a child without exec, so SIGTERM would stop at the
        # shell and cwltool could not stop the containers it started for workflow steps
        --entrypoint cwltool
        "${container}"
        --outdir "${outputs_dir}")
    _append_engine_params cmd_arr
    cmd_arr+=("${wf_url}" "${wf_params}")
    _write_and_run cmd_arr
}

function run_nextflow() {
    local container="nextflow/nextflow:26.10.0"
    # Store NXF_HOME inside the exe_dir so pipeline assets (bin/ scripts, etc.)
    # are on the host-mounted filesystem. Without this, Nextflow caches assets
    # inside the container at /.nextflow/, which is not visible to the host.
    # When child process containers are spawned, Nextflow tries to bind-mount
    # those asset paths from the host, causing "mounts denied" errors.
    local nxf_home="${exe_dir}/nxf_home"
    mkdir -p "${nxf_home}"
    # Write a Nextflow config that propagates DOCKER_API_VERSION into child containers.
    # This is required on Docker Desktop >= 4.x where the minimum supported API version
    # is 1.44, but the Docker client bundled in nextflow/nextflow images reports 1.32.
    local nf_config="${exe_dir}/sapporo.config"
    cat > "${nf_config}" <<'NFCFG'
docker.envWhitelist = 'DOCKER_API_VERSION'
NFCFG
    local -a cmd_arr=(docker run --rm --cidfile "${engine_cid}"
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -e DOCKER_API_VERSION=1.44
        -e "NXF_HOME=${nxf_home}"
        -e "NXF_ASSETS=${nxf_home}/assets"
        -v "${exe_dir}:${exe_dir}"
        -v "${outputs_dir}:${outputs_dir}"
        "${extra_docker_args[@]+"${extra_docker_args[@]}"}"
        "-w=${exe_dir}"
        "${container}"
        nextflow run "${wf_url}" -c "${nf_config}")
    _append_engine_params cmd_arr
    cmd_arr+=(-params-file "${wf_params}" --outdir "${outputs_dir}" -work-dir "${exe_dir}")
    _write_and_run cmd_arr
}

function run_toil() {
    local container="quay.io/ucsc_cgl/toil:9.5.0"
    local -a cmd_arr=(docker run --rm --cidfile "${engine_cid}"
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -e DOCKER_API_VERSION=1.44
        -v "${exe_dir}:${exe_dir}"
        -v "${outputs_dir}:${outputs_dir}"
        "${extra_docker_args[@]+"${extra_docker_args[@]}"}"
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
    local -a cmd_arr=(docker run --rm --cidfile "${engine_cid}"
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -v "${exe_dir}:${exe_dir}"
        -v "${outputs_dir}:${outputs_dir}"
        -v "${tmp_dir}:${tmp_dir}"
        -e "TMPDIR=${tmp_dir}"
        "${extra_docker_args[@]+"${extra_docker_args[@]}"}"
        "-w=${exe_dir}"
        # The image's entrypoint is a shell that runs java as a child without exec, so SIGTERM would stop at
        # the shell. Cromwell in run mode aborts its jobs on SIGTERM when java receives it.
        --entrypoint java
        "${container}"
        --add-opens=java.base/sun.security.util=ALL-UNNAMED "-Djava.io.tmpdir=${tmp_dir}" -jar /app/cromwell.jar run)
    _append_engine_params cmd_arr
    cmd_arr+=("${wf_url}" -i "${wf_params}" -m "${exe_dir}/metadata.json")
    _write_and_run cmd_arr

    # Copy WDL outputs from Cromwell metadata, including the members of Array and struct outputs
    if [[ ! -f "${exe_dir}/metadata.json" ]]; then
        echo "Warning: metadata.json not found" >>"${stderr}"
    else
        while read -r output_file; do
            if [[ -n "${output_file}" && -f "${output_file}" ]]; then
                cp "${output_file}" "${outputs_dir}/" || true
            fi
        done < <(jq -r '.outputs | .. | strings' "${exe_dir}/metadata.json" 2>>"${stderr}")
    fi
}

function run_snakemake() {
    local wf_url_local
    if [[ "${wf_url}" == http://* ]] || [[ "${wf_url}" == https://* ]]; then
        wf_url_local="${exe_dir}/$(basename "${wf_url}")"
        sapporo-cli download "${wf_url}" "${wf_url_local}" || { executor_error $?; }
    elif [[ "${wf_url}" == /* ]]; then
        wf_url_local="${wf_url}"
    else
        wf_url_local="${exe_dir}/${wf_url}"
    fi

    local container="snakemake/snakemake:v9.27.0"
    local -a docker_arr=(docker run --rm --cidfile "${engine_cid}"
        -v "${exe_dir}:${exe_dir}"
        -v "${outputs_dir}:${outputs_dir}"
        "${extra_docker_args[@]+"${extra_docker_args[@]}"}"
        "-w=${exe_dir}"
        "${container}")
    local -a cmd_arr=("${docker_arr[@]}" snakemake)
    _append_engine_params cmd_arr
    cmd_arr+=(--configfile "${wf_params}" --snakefile "${wf_url_local}")
    _write_and_run cmd_arr

    # The output files are listed by a second container and filtered here, so that no shell inside the
    # container receives the engine parameters. A failed listing leaves outputs/ empty.
    local -a summary_arr=("${docker_arr[@]}" snakemake --configfile "${wf_params}" --snakefile "${wf_url_local}" --summary)
    rm -f "${engine_cid}"
    while read -r file_path; do
        if [[ -z "${file_path}" ]] || [[ "${file_path}" == *".."* ]] || [[ "${file_path}" == /* ]]; then
            echo "Warning: Skipping suspicious output path: ${file_path}" >>"${stderr}"
            continue
        fi
        local dir_path
        dir_path=$(dirname "${file_path}")
        mkdir -p "${outputs_dir}/${dir_path}"
        cp "${exe_dir}/${file_path}" "${outputs_dir}/${file_path}" 2>/dev/null || true
    done < <("${summary_arr[@]}" 2>/dev/null | tail -n +2 | cut -f 1 || true)
}

function run_ep3() {
    local container="ghcr.io/tom-tan/ep3:v1.7.0"
    local -a cmd_arr=(docker run --rm --cidfile "${engine_cid}"
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -e DOCKER_API_VERSION=1.44
        -v "${exe_dir}:${exe_dir}"
        -v "${outputs_dir}:${outputs_dir}"
        -v "${tmp_dir}:${tmp_dir}"
        -e "TMPDIR=${tmp_dir}"
        "${extra_docker_args[@]+"${extra_docker_args[@]}"}"
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
    local container="alphaunito/streamflow:0.2.0rc3"
    local -a cmd_arr=(docker run --rm --cidfile "${engine_cid}"
        -v /var/run/docker.sock:/var/run/docker.sock
        -e DOCKER_HOST=unix:///var/run/docker.sock
        -v "${docker_stage}:/usr/bin/docker:ro"
        -v "${exe_dir}:${exe_dir}"
        -v "${outputs_dir}:${outputs_dir}"
        -v "${tmp_dir}:${tmp_dir}"
        -e "TMPDIR=${tmp_dir}"
        "${extra_docker_args[@]+"${extra_docker_args[@]}"}"
        "-w=${exe_dir}"
        "${container}"
        cwl-runner --outdir "${outputs_dir}")
    _append_engine_params cmd_arr
    cmd_arr+=("${wf_url}" "${wf_params}")
    _write_and_run cmd_arr
}

function cancel() {
    # Edit this function for environment-specific cancellation procedures.
    # cancel_docker_engine stops the engine container that the bundled run_<engine>() functions
    # start. stop_run_wf then sends SIGTERM to the process group of run_wf (the engine process and
    # everything it started on this host) and SIGKILL after the grace period. Work that lives
    # elsewhere, such as a Slurm job or containers that the engine itself started for workflow
    # steps, needs a cancel_<engine>() function.
    cancel_docker_engine
    local hook="cancel_${wf_engine}"
    if [[ "$(type -t "${hook}")" == "function" ]]; then
        "${hook}"
    fi
    stop_run_wf
}

function cancel_docker_engine() {
    # The bundled run_<engine>() functions pass `--cidfile "${engine_cid}"` to `docker run`, because
    # an engine inside a container does not always exit on SIGTERM and the container outlives the
    # `docker run` client. The id is trusted only if the container was started for this run's
    # exe directory, since the run directory is writable from inside the engine container.
    if [[ ! -s "${engine_cid}" ]]; then
        return 0
    fi
    local container_id
    container_id=$(cat "${engine_cid}")
    local workdir
    workdir=$(docker inspect -f '{{.Config.WorkingDir}}' "${container_id}" 2>/dev/null || true)
    if [[ "${workdir}" == "${exe_dir}" ]]; then
        # SIGTERM first, so that the engine can stop the containers it started for workflow steps
        docker stop -t "${cancel_grace_seconds}" "${container_id}" >/dev/null 2>&1 || true
    fi
}

function cancel_cwltool() {
    # Add specific cancellation procedures for cwltool if needed
    :
}

function upload() {
    # Edit this function for environment-specific upload procedures
    :
}

function set_extra_docker_args() {
    # Edit this function to choose extra `docker run` flags for each run, for example to mount only the
    # data that the workflow of this run may read. ${wf_engine}, ${wf_url} and ${run_dir}/username.txt
    # (written when authentication is enabled) describe the run. The default splits
    # SAPPORO_EXTRA_DOCKER_ARGS on whitespace and applies it to every run.
    extra_docker_args=()
    if [[ -n "${SAPPORO_EXTRA_DOCKER_ARGS:-}" ]]; then
        read -ra extra_docker_args <<< "${SAPPORO_EXTRA_DOCKER_ARGS}"
    fi
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
engine_cid="${run_dir}/engine.cid"
tmp_dir="${run_dir}/tmp"

# Extract workflow engine and URL from the run request
wf_engine=$(jq -r ".workflow_engine" "${run_request}")
wf_url=$(jq -r ".workflow_url" "${run_request}")
wf_engine_params=$(head -n 1 "${wf_engine_params_file}")

# Seconds between SIGTERM and SIGKILL when a run is canceled or run.sh is shut down
cancel_grace_seconds="${SAPPORO_CANCEL_GRACE_SECONDS:-30}"

# Set by set_extra_docker_args when run_wf starts
extra_docker_args=()

function generate_outputs_list() {
    sapporo-cli dump-outputs "${run_dir}" || { executor_error $?; }
}

function generate_ro_crate() {
    sapporo-cli generate-ro-crate "${run_dir}" 2>>"${stderr}" \
        || _write_control_file "${ro_crate}" '{"@error": "RO-Crate generation failed. Check stderr.log for details."}'
    # If you want to upload ro-crate-metadata.json, write the process here.
}

function _write_control_file() {
    # Write $2 to the control file $1. The run directory is writable from inside the engine container,
    # so a symlink left in place of a control file is removed instead of being written through.
    local path=$1
    if [[ -L "${path}" ]]; then
        rm -f -- "${path}"
    fi
    printf '%s\n' "$2" >"${path}"
}

function _current_state() {
    cat "${state}" 2>/dev/null || true
}

function _owns_outcome() {
    # True while run_wf still owns the outcome of the run. Once a signal handler in the parent
    # process has written CANCELING or SYSTEM_ERROR, run_wf must not write a terminal state over it.
    local current
    current=$(_current_state)
    [[ "${current}" == "QUEUED" || "${current}" == "RUNNING" ]]
}

function _write_outcome() {
    local code=$1
    local new_state=$2
    _write_control_file "${exit_code}" "${code}"
    _write_control_file "${end_time}" "$(date -u +"%Y-%m-%dT%H:%M:%S")"
    _write_control_file "${state}" "${new_state}"
}

function stop_run_wf() {
    # Stop run_wf and everything it started: SIGTERM to its process group, SIGKILL to whatever is
    # still alive after the grace period. Attached `docker run`, `podman run` and `srun` forward
    # SIGTERM to what they run.
    if [[ -z "${bg_pid:-}" ]]; then
        return 0
    fi
    kill -TERM -- "-${bg_pid}" 2>/dev/null || true
    wait "${bg_pid}" 2>/dev/null || true
    local remaining_ticks=$((cancel_grace_seconds * 5))
    while kill -0 -- "-${bg_pid}" 2>/dev/null && ((remaining_ticks > 0)); do
        sleep 0.2
        remaining_ticks=$((remaining_ticks - 1))
    done
    kill -KILL -- "-${bg_pid}" 2>/dev/null || true
}

function desc_error() {
    # ERR trap: an unexpected failure in run.sh itself. set -E applies it inside run_wf as well.
    local original_exit_code=1
    _owns_outcome || exit "${original_exit_code}"
    _write_outcome "${original_exit_code}" "SYSTEM_ERROR"
    exit "${original_exit_code}"
}

function executor_error() {
    local original_exit_code=${1:-1}
    _owns_outcome || exit "${original_exit_code}"
    _write_outcome "${original_exit_code}" "EXECUTOR_ERROR"
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
    if _owns_outcome; then
        _write_control_file "${state}" "SYSTEM_ERROR"
        cancel
        _write_outcome "${original_exit_code}" "SYSTEM_ERROR"
    fi
    exit "${original_exit_code}"
}

function cancel_by_request() {
    # USR1 trap: POST /runs/${run_id}/cancel writes CANCELING to state.txt and then sends SIGUSR1
    local original_exit_code=138
    if ! _owns_outcome && [[ "$(_current_state)" != "CANCELING" ]]; then
        exit "${original_exit_code}"
    fi
    _write_control_file "${state}" "CANCELING"
    cancel
    _write_outcome "${original_exit_code}" "CANCELED"
    exit "${original_exit_code}"
}

function check_canceling() {
    # The run was canceled before run.sh started, so there is nothing to stop
    if [[ "$(_current_state)" == "CANCELING" ]]; then
        _write_outcome 138 "CANCELED"
        exit 138
    fi
}

trap 'desc_error' ERR
trap 'kill_by_system SIGHUP' HUP
trap 'kill_by_system SIGINT' INT
trap 'kill_by_system SIGQUIT' QUIT
trap 'kill_by_system SIGTERM' TERM
trap 'cancel_by_request' USR1

# The pid is written after the traps are set, so that a cancel that finds run.pid can send SIGUSR1
# safely. A cancel that comes earlier leaves CANCELING in state.txt, which check_canceling picks up.
_write_control_file "${run_dir}/run.pid" "$$"

# Run the workflow as a background job so that this process stays free to handle signals
run_wf </dev/null &
bg_pid=$!
wait "${bg_pid}" || true
