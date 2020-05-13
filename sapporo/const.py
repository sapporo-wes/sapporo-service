#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path
from typing import Dict

SRC_DIR: Path = Path(__file__).parent.resolve()

SERVICE_INFO_JSON: Path = \
    SRC_DIR.joinpath("service-info.json").resolve()
WORKFLOWS_JSON: Path = \
    SRC_DIR.joinpath("workflows.json").resolve()
RUN_SH: Path = \
    SRC_DIR.joinpath("run.sh").resolve()
DEFAULT_RUN_DIR = Path.cwd().parent.joinpath("run").resolve()
DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 8080
GET_STATUS_CODE: int = 200
POST_STATUS_CODE: int = 200
DATE_FORMAT: str = "%Y-%m-%dT%H:%M:%S"
CANCEL_TIMEOUT: int = 10

RUN_DIR_STRUCTURE: Dict[str, str] = {
    "run_request": "run_request.json",
    "state": "state.txt",
    "exe": "exe",
    "output": "output",
    "wf_params": "exe/workflow_params.json",
    "start_time": "start_time.txt",
    "end_time": "end_time.txt",
    "exit_code": "exit_code.txt",
    "stdout": "stdout.log",
    "stderr": "stderr.log",
    "pid": "run.pid",
    "cmd": "cmd.txt",
    "sys_error": "sys_error.log",
    "tasks": "tasks"
}
