#!/usr/local/bin/python3
# coding: utf-8
from pathlib import Path
from typing import Any

import yaml

SERVICE_BASE_DIR = Path(__file__).absolute().parent.parent.parent.parent
RUN_BASE_DIR = SERVICE_BASE_DIR.joinpath("run")
RUN_EXECUTION_SCRIPT_PATH = SERVICE_BASE_DIR.joinpath("src/run_workflow.sh")

LOG_FILE_PATH = SERVICE_BASE_DIR.joinpath("log/app/flask.log")
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

SECRET_KEY_FILE_PATH = SERVICE_BASE_DIR.joinpath("src/app/secret_key.txt")
TOKEN_LIST_FILE_PATH = SERVICE_BASE_DIR.joinpath("src/app/token_list.txt")

SERVICE_INFO_FILE_PATH = SERVICE_BASE_DIR.joinpath("service-info.yml")
WORKFLOW_INFO_FILE_PATH = SERVICE_BASE_DIR.joinpath("workflow-info.yml")

RUN_ORDER_FILE_NAME = "run_order.yml"
WORKFLOW_FILE_NAME = "workflow"
WORKFLOW_PARAMETERS_FILE_NAME = "workflow_parameters"
UPLOAD_INFO_FILE_NAME = "upload_info"
PID_INFO_FILE_NAME = "run.pid"

OUTPUT_DIR_NAME = "output"
STATUS_FILE_NAME = "status.txt"
STDOUT_FILE_NAME = "stdout.log"
STDERR_FILE_NAME = "stderr.log"
UPLOAD_URL_FILE_NAME = "upload_url.txt"

RUN_SHELL_STDOUT_FILE_NAME = "run_shell.stdout.log"
RUN_SHELL_STDERR_FILE_NAME = "run_shell.stderr.log"


def read_workflow_info() -> Any:
    with WORKFLOW_INFO_FILE_PATH.open(mode="r") as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


def read_service_info() -> Any:
    with SERVICE_INFO_FILE_PATH.open(mode="r") as f:
        return yaml.load(f, Loader=yaml.SafeLoader)
