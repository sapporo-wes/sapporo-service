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

echo "--- ${BASE_DIR}/sapporo ---"
mypy --strict \
    --allow-untyped-calls \
    --allow-untyped-decorators \
    --ignore-missing-imports \
    --no-warn-unused-ignores \
    --implicit-reexport \
    ${BASE_DIR}/sapporo

echo "--- ${BASE_DIR}/tests/pytest ---"
mypy --strict \
    --allow-untyped-calls \
    --allow-untyped-decorators \
    --ignore-missing-imports \
    --no-warn-unused-ignores \
    --implicit-reexport \
    ${BASE_DIR}/tests/unit_test

echo "--- ${BASE_DIR}/setup.py ---"
mypy --strict \
    --allow-untyped-calls \
    --allow-untyped-decorators \
    --ignore-missing-imports \
    --no-warn-unused-ignores \
    --implicit-reexport \
    ${BASE_DIR}/setup.py
