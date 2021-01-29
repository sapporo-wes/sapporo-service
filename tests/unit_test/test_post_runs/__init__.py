#!/usr/bin/env python3
# coding: utf-8
import json
import shlex
import subprocess as sp
from pathlib import Path

from sapporo.type import RunLog, RunStatus

from ..conftest import TEST_HOST, TEST_PORT

SCRIPT_DIR = \
    Path(__file__).parent.parent.parent.joinpath("curl_example").resolve()


def get_run_id(run_id: str) -> RunLog:
    script_path = SCRIPT_DIR.joinpath("get_run_id.sh")
    proc = sp.run(shlex.split(f"/bin/bash {str(script_path)} {run_id}"),
                  capture_output=True,
                  encoding="utf-8",
                  env={"SAPPORO_HOST": TEST_HOST,
                       "SAPPORO_PORT": TEST_PORT})
    assert proc.returncode == 0
    res_data: RunLog = json.loads(proc.stdout)

    return res_data


def get_run_id_status(run_id: str) -> RunStatus:
    script_path = SCRIPT_DIR.joinpath("get_status.sh")
    proc = sp.run(shlex.split(f"/bin/bash {str(script_path)} {run_id}"),
                  capture_output=True,
                  encoding="utf-8",
                  env={"SAPPORO_HOST": TEST_HOST,
                       "SAPPORO_PORT": TEST_PORT})
    assert proc.returncode == 0
    res_data: RunStatus = json.loads(proc.stdout)

    return res_data
