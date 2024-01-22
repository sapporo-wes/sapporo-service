#!/usr/bin/env bash
set -euo pipefail

run_mypy() {
    echo "=== ${1} ==="
    mypy --strict \
        --allow-untyped-decorators \
        --follow-imports=skip \
        --ignore-missing-imports \
        --implicit-reexport \
        --no-warn-unused-ignores \
        "${1}" || true

}

PACKAGE_ROOT="$(cd "$(dirname "$0")" && pwd)"
while [[ "${PACKAGE_ROOT}" != "/" && ! -f "${PACKAGE_ROOT}/setup.py" ]]; do
    PACKAGE_ROOT="$(dirname "${PACKAGE_ROOT}")"
done

echo "${PACKAGE_ROOT}"

cd "${PACKAGE_ROOT}"

run_mypy "${PACKAGE_ROOT}/sapporo"
run_mypy "${PACKAGE_ROOT}/tests/unit_test"
run_mypy "${PACKAGE_ROOT}/setup.py"
