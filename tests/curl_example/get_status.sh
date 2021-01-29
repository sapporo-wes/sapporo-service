#!/usr/bin/env bash
set -Eeu

if [[ $# != 1 ]]; then
  echo "[Error] Usage: $(basename ${BASH_SOURCE[0]}) run_id"
  exit 1
fi

curl -fsSL -X GET http://${SAPPORO_HOST}:${SAPPORO_PORT}/runs/${1}/status
