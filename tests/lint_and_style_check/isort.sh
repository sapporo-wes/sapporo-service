#!/bin/bash
set -eu

SCRIPT_DIR=$(
    cd $(dirname $0)
    pwd
)
BASE_DIR=$(
    cd ${SCRIPT_DIR}/../..
    pwd
)

isort ${BASE_DIR} \
    --skip "${BASE_DIR}/tests/resources" \
    --check
