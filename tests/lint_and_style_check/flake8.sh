#!/bin/bash
SCRIPT_DIR=$(
    cd $(dirname $0)
    pwd
)
BASE_DIR=$(
    cd ${SCRIPT_DIR}/../..
    pwd
)

flake8 ${BASE_DIR} --count --show-source --statistics
