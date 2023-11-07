#!/usr/bin/env bash
set -eu

get_dir() {
    cd $(dirname $1)
    pwd
}

SCRIPT_DIR=$(get_dir $0)
BASE_DIR=$(get_dir "${SCRIPT_DIR}/../../..")

cd ${BASE_DIR}

flake8 ${BASE_DIR} \
    --extend-ignore=E501 \
    --exclude "${BASE_DIR}/tests/resources" \
    --count --show-source --statistics
