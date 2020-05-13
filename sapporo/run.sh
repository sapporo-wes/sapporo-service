#!/bin/bash
set -eEux

function run_wf() {
    if [[ ${execution_engine} == "cwltool" ]]; then
        run_cwltool
    fi
}

function run_cwltool() {
    echo "RUNNING" >${status}
    local container="commonworkflowlanguage/cwltool:1.0.20191225192155"
    ${DOCKER_CMD} ${container} --custom-net=sapporo-network --outdir /work/output workflow workflow_parameters 1>${stdout} 2>${stderr}
    echo "COMPLETE" >${status}
    exit 0
}

function cancel() {
    if [[ ${execution_engine} == "cwltool" ]]; then
        cancel_cwltool
    fi
}

function cancel_cwltool() {
    exit 1
}

# =============

# Sibling docker command
D_NETWORK_OPT="--network=sapporo-network"
D_SOCK="-v /var/run/docker.sock:/var/run/docker.sock"
D_TMP="-v /tmp:/tmp"
DOCKER_CMD="docker run -i --rm ${D_NETWORK_OPT} ${D_SOCK} ${D_TMP} -v ${run_dir}:${run_dir} -w=${run_dir}/exe"

trap 'echo "SYSTEM_ERROR" >${status}; exit 1' 1 2 3 15
trap 'cancel' 10
trap 'echo "EXECUTOR_ERROR" >${status}; exit 1' ERR

run_wf
