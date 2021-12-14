#!/usr/bin/env bash
set -eu

SCRIPT_DIR=$(
    cd $(dirname $0)
    pwd
)
BASE_DIR=$(
    cd ${SCRIPT_DIR}/../..
    pwd
)

cd ${BASE_DIR}

flake8 ${BASE_DIR} \
    --extend-ignore=E501 \
    --exclude "${BASE_DIR}/tests/resources" \
    --count --show-source --statistics
