#!/usr/bin/env bash

# This is a test runner for sapporo/ro-crate.py. It executes workflow runs
# under tests/curl_example and checks the RO-Crate generated for each run.
# Assumptions:
#   - run_dir exists at ../../run (library root)
#   - sapporo is running at 127.0.0.1:1122
#   - this script is executed from the Host OS

set -euo pipefail

# set -x

# Define constants for readability and maintenance
PACKAGE_ROOT="$(cd "$(dirname "$0")" && pwd)"
while [[ "${PACKAGE_ROOT}" != "/" && ! -f "${PACKAGE_ROOT}/setup.py" ]]; do
  PACKAGE_ROOT="$(dirname "${PACKAGE_ROOT}")"
done
readonly RUN_DIR=${PACKAGE_ROOT}/run
readonly WF_DIR=${PACKAGE_ROOT}/tests/curl_example
SAPPORO_HOST="127.0.0.1"
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
  local wf_script=$1
  local wf_name=$(basename ${wf_script} .sh)
  local response=$(bash ${wf_script})
  local json_response=$(echo "${response}" | awk '/{/,/}/')
  local run_id=$(echo "${json_response}" | jq -r .run_id)
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
  for wf_script in $(ls ${WF_DIR}/*.sh); do
    run_workflow ${wf_script}
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
