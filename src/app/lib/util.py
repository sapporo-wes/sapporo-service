#!/usr/local/bin/python3
# coding: utf-8
from pathlib import Path

import yaml

SERVICE_BASE_DIR = Path(__file__).absolute().parent.parent.parent.parent

LOG_FILE_PATH = SERVICE_BASE_DIR.joinpath("log/app/flask.log")
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

SECRET_KEY_FILE_PATH = SERVICE_BASE_DIR.joinpath("src/app/secret_key.txt")
TOKEN_LIST_FILE_PATH = SERVICE_BASE_DIR.joinpath("src/app/token_list.txt")

SERVICE_INFO_FILE_PATH = SERVICE_BASE_DIR.joinpath("service-info.yml")
WORKFLOW_INFO_FILE_PATH = SERVICE_BASE_DIR.joinpath("workflow-info.yml")

RUN_BASE_DIR = SERVICE_BASE_DIR.joinpath("run")
RUN_BASE_DIR.mkdir(parents=True, exist_ok=True)
RUN_ORDER_FILE_NAME = "run_order.yml"
WORKFLOW_FILE_NAME = "workflow"
WORKFLOW_PARAMETERS_FILE_NAME = "workflow_parameters"
UPLOAD_INFO_FILE_NAME = "upload_info"
STATUS_FILE_NAME = "status.txt"
PID_INFO_FILE_NAME = "run.pid"
UPLOAD_URL_FILE_NAME = "upload_url.txt"
OUTPUT_DIR_NAME = "output"
STDOUT_FILE_NAME = "stdout.log"
STDERR_FILE_NAME = "stderr.log"
RUN_SHELL_STDOUT_FILE_NAME = "run_shell.stdout.log"
RUN_SHELL_STDERR_FILE_NAME = "run_shell.stderr.log"

RUN_EXECUTION_SCRIPT_PATH = SERVICE_BASE_DIR.joinpath("src/run_workflow.sh")

SUPPORTED_WES_VERSIONS = ["SapporoWES-v1.0.0"]


def read_workflow_info():
    with WORKFLOW_INFO_FILE_PATH.open(mode="r") as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


def read_service_info():
    with SERVICE_INFO_FILE_PATH.open(mode="r") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
    data["supported_wes_versions"] = SUPPORTED_WES_VERSIONS
    return data
