#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

run_check() {
    echo "--- $1 check ---"
    /bin/bash "${SCRIPT_DIR}/$1.sh"
}

echo "Start lint and style check..."

run_check "flake8"
run_check "isort"
run_check "mypy"

echo "Finish lint and style check..."
