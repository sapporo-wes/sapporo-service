#!/usr/bin/env bash
set -eu

get_dir() {
    cd $(dirname $1)
    pwd
}

SCRIPT_DIR=$(get_dir $0)
BASE_DIR=$(get_dir "${SCRIPT_DIR}/../../..")

cd ${BASE_DIR}

isort "${BASE_DIR}" --skip "${BASE_DIR}/tests/resources" --check
