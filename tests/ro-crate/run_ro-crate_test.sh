#!/usr/bin/env bash

# This is a test runner for sapporo/ro-crate.py. It executes workflow runs
# under tests/curl_example/post_runs and checks the RO-Crate generated for each run.
# Assumptions:
#   - run_dir exists at ../../run (library root)
#   - sapporo is running at 0.0.0.0:1122
#   - this script is executed from the Host OS

set -euo pipefail

# Define constants for readability and maintenance
readonly HERE=$(cd $(dirname $0) && pwd)
readonly ROOT_DIR=$(cd ${HERE}/../.. && pwd)
readonly RUN_DIR=${ROOT_DIR}/run
readonly WF_DIR=${ROOT_DIR}/tests/curl_example/post_runs
SAPPORO_HOST="0.0.0.0"
SAPPORO_PORT=1122
readonly RUNNING_STATUS=("QUEUED" "INITIALIZING" "RUNNING")

# Declare associative arrays
declare -A wf_name_to_run_id
declare -A wf_name_to_run_status
declare -A wf_name_to_ro_crate_status
declare -a wf_name_failed_to_generate_ro_crate

# Check if Sapporo is running
function check_sapporo() {
  echo "=== Check sapporo is running... ==="
  curl -fsSL http://${SAPPORO_HOST}:${SAPPORO_PORT}/service-info >/dev/null
}

# Run workflow
function run_workflow() {
  local wf_dir=$1
  local wf_name=$(sed -e "s|${WF_DIR}/||g" <<<${wf_dir})
  local post_script=${wf_dir}/post_runs.sh

  echo "Running workflow: ${wf_name}"
  local response=$(SAPPORO_HOST=${SAPPORO_HOST} SAPPORO_PORT=${SAPPORO_PORT} bash ${post_script})
  local run_id=$(jq -r .run_id <<<${response})
  echo "Run ID: ${run_id}"
  wf_name_to_run_id[${wf_name}]=${run_id}
}

# Check if run is still running
function is_run_still_running() {
  local status=$1
  [[ " ${RUNNING_STATUS[@]} " =~ " ${status} " ]]
}

# Execute all workflows
function execute_all_workflows() {
  echo "=== Run all workflows... ==="
  local wf_dirs=$(find ${WF_DIR} -maxdepth 2 -mindepth 2 -type d | grep -v with_docker)
  for wf_dir in ${wf_dirs}; do
    run_workflow ${wf_dir}
  done
}

# Wait for all runs to finish
function wait_for_all_runs_to_finish() {
  echo "=== Wait for all runs to finish... ==="
  for wf_name in ${!wf_name_to_run_id[@]}; do
    local run_id=${wf_name_to_run_id[${wf_name}]}
    echo "Waiting for ${wf_name} (run_id: ${run_id}) to finish..."
    while true; do
      local response=$(curl -fsSL http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs/${run_id}/status)
      local status=$(jq -r .state <<<${response})
      if is_run_still_running "${status}"; then
        sleep 3
      else
        echo "Finished with ${status}"
        wf_name_to_run_status[${wf_name}]=${status}
        break
      fi
    done
  done
}

# Check RO-Crate for each run
function check_ro_crate_for_each_run() {
  echo "=== Check RO-Crate... ==="
  for wf_name in ${!wf_name_to_run_status[@]}; do
    local run_id=${wf_name_to_run_id[${wf_name}]}
    local status=${wf_name_to_run_status[${wf_name}]}
    local run_dir=${RUN_DIR}/${run_id:0:2}/${run_id}
    local ro_crate=${run_dir}/ro-crate-metadata.json

    if [[ ${status} == "COMPLETE" ]]; then
      # If ro-crate is "{}", it has failed
      if [[ $(jq -r . <<<$(cat ${ro_crate})) == "{}" ]]; then
        echo "${wf_name} (run_id: ${run_id}) failed to generate RO-Crate"
        wf_name_to_ro_crate_status[${wf_name}]="Failed to generate RO-Crate"
        wf_name_failed_to_generate_ro_crate+=(${wf_name})
      else
        echo "${wf_name} (run_id: ${run_id}) succeeded"
        wf_name_to_ro_crate_status[${wf_name}]="Succeeded"
      fi
    else
      echo "${wf_name} (run_id: ${run_id}) failed to run workflow itself (status: ${status})"
      wf_name_to_ro_crate_status[${wf_name}]="Failed to run workflow itself (status: ${status})"
    fi
  done
}

# Print a summary
function print_summary() {
  echo "=== Summary ==="
  for wf_name in ${!wf_name_to_ro_crate_status[@]}; do
    echo "${wf_name}: ${wf_name_to_ro_crate_status[${wf_name}]}"
  done
}

# Print debug commands for runs that failed to generate RO-Crate
function print_debug_commands_for_failed_runs() {
  if [[ -n ${wf_name_failed_to_generate_ro_crate+x} && ${#wf_name_failed_to_generate_ro_crate[@]} -gt 0 ]]; then
    echo "=== Debug commands for runs that failed to generate RO-Crate ==="
    for wf_name in ${wf_name_failed_to_generate_ro_crate[@]}; do
      local run_id=${wf_name_to_run_id[${wf_name}]}
      echo "  - ${wf_name}: \`python3 ./sapporo/ro-crate.py ./run/${run_id:0:2}/${run_id}\`"
    done
  fi
}

# Start of the script
check_sapporo
execute_all_workflows
wait_for_all_runs_to_finish
check_ro_crate_for_each_run
print_summary
print_debug_commands_for_failed_runs

echo "=== Done ==="

# Exit with error if there are runs that failed to generate RO-Crate
if [[ -n ${wf_name_failed_to_generate_ro_crate+x} && ${#wf_name_failed_to_generate_ro_crate[@]} -gt 0 ]]; then
  exit 1
else
  exit 0
fi
