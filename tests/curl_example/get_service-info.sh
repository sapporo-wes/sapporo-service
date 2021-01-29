#!/usr/bin/env bash
set -Eeu

curl -fsSL -X GET http://${SAPPORO_HOST}:${SAPPORO_PORT}/service-info
