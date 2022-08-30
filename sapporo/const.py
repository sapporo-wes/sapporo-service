#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path
from typing import Dict, Literal

SRC_DIR: Path = Path(__file__).parent.resolve()

DEFAULT_SERVICE_INFO: Path = SRC_DIR.joinpath("service-info.json").resolve()
DEFAULT_EXECUTABLE_WORKFLOWS: Path = \
    SRC_DIR.joinpath("executable_workflows.json").resolve()
DEFAULT_RUN_SH: Path = SRC_DIR.joinpath("run.sh").resolve()
DEFAULT_RUN_DIR = Path.cwd().joinpath("run").resolve()
DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 1122
DEFAULT_ACCESS_CONTROL_ALLOW_ORIGIN: str = "*"
DEFAULT_URL_PREFIX: str = "/"
GET_STATUS_CODE: int = 200
POST_STATUS_CODE: int = 200
DATE_FORMAT: str = "%Y-%m-%dT%H:%M:%S"

SERVICE_INFO_SCHEMA: Path = \
    SRC_DIR.joinpath("service-info.schema.json").resolve()
EXECUTABLE_WORKFLOWS_SCHEMA: Path = \
    SRC_DIR.joinpath("executable_workflows.schema.json").resolve()

RUN_DIR_STRUCTURE: Dict[str, str] = {
    "sapporo_config": "sapporo_config.json",
    "run_request": "run_request.json",
    "state": "state.txt",
    "exe_dir": "exe",
    "outputs_dir": "outputs",
    "outputs": "outputs.json",
    "wf_params": "exe/workflow_params.json",
    "start_time": "start_time.txt",
    "end_time": "end_time.txt",
    "exit_code": "exit_code.txt",
    "stdout": "stdout.log",
    "stderr": "stderr.log",
    "pid": "run.pid",
    "wf_engine_params": "workflow_engine_params.txt",
    "cmd": "cmd.txt",
    "task_logs": "task.log",
    "service_info": "service_info.json",
    "executable_workflows": "executable_workflows.json",
    "run_sh": "run.sh",
    "yevis_metadata": "yevis-metadata.yml",
}

RUN_DIR_STRUCTURE_KEYS = Literal[
    "sapporo_config",
    "run_request",
    "state",
    "exe_dir",
    "outputs_dir",
    "outputs",
    "wf_params",
    "start_time",
    "end_time",
    "exit_code",
    "stdout",
    "stderr",
    "pid",
    "wf_engine_params",
    "cmd",
    "task_logs",
    "service_info",
    "executable_workflows",
    "run_sh",
    "yevis_metadata",
]
