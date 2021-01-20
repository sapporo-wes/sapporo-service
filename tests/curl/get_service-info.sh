#!/usr/bin/env bash
set -Eeu

curl -fsSL -X GET http://localhost:${SAPPORO_PORT}/service-info
