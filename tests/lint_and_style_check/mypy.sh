#!/bin/bash
SCRIPT_DIR=$(
    cd $(dirname $0)
    pwd
)
BASE_DIR=$(
    cd ${SCRIPT_DIR}/../..
    pwd
)

mypy --strict \
    --allow-untyped-calls \
    --allow-untyped-decorators \
    --ignore-missing-imports \
    --no-warn-unused-ignores \
    ${BASE_DIR}
