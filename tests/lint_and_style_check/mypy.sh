#!/usr/bin/env bash
set -eu

get_dir() {
    cd $(dirname $1)
    pwd
}

run_mypy() {
    echo "--- ${1} ---"
    mypy --strict \
        --allow-untyped-calls \
        --allow-untyped-decorators \
        --ignore-missing-imports \
        --no-warn-unused-ignores \
        --implicit-reexport \
        $1
}

SCRIPT_DIR=$(get_dir $0)
BASE_DIR=$(get_dir "${SCRIPT_DIR}/../../..")

cd ${BASE_DIR}

run_mypy "${BASE_DIR}/sapporo"
run_mypy "${BASE_DIR}/tests/unit_test"
run_mypy "${BASE_DIR}/setup.py"
