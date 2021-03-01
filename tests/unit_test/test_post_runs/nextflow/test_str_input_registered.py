#!/usr/bin/env python3
# coding: utf-8
import json
import shlex
import subprocess
from time import sleep

from sapporo.type import RunId

from . import SCRIPT_DIR, TEST_HOST, TEST_PORT  # type: ignore


def post_runs_str_input_registered() -> RunId:
    script_path = SCRIPT_DIR.joinpath("str_input_registered/post_runs.sh")
    proc = subprocess.run(shlex.split(f"/bin/bash {str(script_path)}"),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          encoding="utf-8",
                          env={"SAPPORO_HOST": TEST_HOST,
                               "SAPPORO_PORT": TEST_PORT})
    assert proc.returncode == 0
    res_data: RunId = json.loads(proc.stdout)

    return res_data


def test_str_input_registered(setup_test_server_registered_only_mode: None) \
        -> None:
    res_data = post_runs_str_input_registered()
    assert "run_id" in res_data
    run_id = res_data["run_id"]

    from .. import get_run_id_status
    count = 0
    while count <= 120:
        get_status_data = get_run_id_status(run_id)
        if str(get_status_data["state"]) in \
                ["COMPLETE", "EXECUTOR_ERROR", "SYSTEM_ERROR", "CANCELED"]:
            break
        sleep(3)
        count += 1
    assert str(get_status_data["state"]) == "COMPLETE"

    from .. import get_run_id
    data = get_run_id(run_id)

    assert data["request"]["tags"] == "{}"
    assert data["request"]["workflow_engine_name"] == "nextflow"
    assert data["request"]["workflow_engine_parameters"] == "{}"
    assert data["request"]["workflow_name"] == "nextflow_str_input"
    assert data["request"]["workflow_params"] == \
        "{\n  \"str\": \"sapporo-nextflow-str-input\"\n}\n"
    assert data["request"]["workflow_type"] == "Nextflow"
    assert data["request"]["workflow_type_version"] == "v1.0"
    assert data["request"]["workflow_url"] == "./str_input.nf"
    assert data["run_id"] == run_id
    assert data["run_log"]["exit_code"] == 0
    assert data["run_log"]["name"] == "nextflow_str_input"
    assert "[100%] 1 of 1" in data["run_log"]["stdout"]
    assert str(data["state"]) == "COMPLETE"
    assert data["task_logs"] is None
