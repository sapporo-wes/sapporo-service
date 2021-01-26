#!/usr/bin/env bash
set -eu
SCRIPT_DIR=$(
    cd $(dirname $0)
    pwd
)

echo "Start lint and style check..."

echo "--- flake8 check ---"
/bin/bash ${SCRIPT_DIR}/flake8.sh
echo "--- isort check ---"
/bin/bash ${SCRIPT_DIR}/isort.sh
echo "--- mypy check ---"
/bin/bash ${SCRIPT_DIR}/mypy.sh

echo "Finish lint and style check..."
