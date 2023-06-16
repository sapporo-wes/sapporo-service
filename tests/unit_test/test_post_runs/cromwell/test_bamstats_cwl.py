#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=subprocess-run-check, unused-argument, import-outside-toplevel
import json
import shlex
import subprocess
from time import sleep

from sapporo.model import RunId

from . import SCRIPT_DIR, TEST_HOST, TEST_PORT


def post_runs_bamstats_cwl() -> RunId:
    script_path = \
        SCRIPT_DIR.joinpath("bamstats_cwl/post_runs.sh")
    proc = subprocess.run(shlex.split(f"/bin/bash {str(script_path)}"),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          encoding="utf-8",
                          env={"SAPPORO_HOST": TEST_HOST,
                               "SAPPORO_PORT": TEST_PORT})
    assert proc.returncode == 0
    res_data: RunId = json.loads(proc.stdout)

    return res_data


def test_bamstats_cwl(setup_test_server: None) -> None:
    res_data = post_runs_bamstats_cwl()
    assert "run_id" in res_data
    run_id = res_data["run_id"]

    from .. import get_run_id_status
    count = 0
    while count <= 120:
        sleep(3)
        get_status_data = get_run_id_status(run_id)
        if str(get_status_data["state"]) in \
                ["COMPLETE", "EXECUTOR_ERROR", "SYSTEM_ERROR", "CANCELED"]:
            break
        count += 1
    assert str(get_status_data["state"]) == "COMPLETE"

    from .. import get_run_id
    data = get_run_id(run_id)

    assert len(data["outputs"]) == 1
    assert data["request"]["tags"] == "{\n  \"workflow_name\": \"dockstore-tool-bamstats-cwl\"\n}\n"
    wf_attachment = \
        json.loads(data["request"]["workflow_attachment"])  # type: ignore
    assert len(wf_attachment) == 2
    assert data["request"]["workflow_engine_name"] == "cromwell"
    assert data["request"]["workflow_engine_parameters"] is None
    assert data["request"]["workflow_name"] is None
    assert data["request"]["workflow_type"] == "CWL"
    assert data["request"]["workflow_type_version"] == "v1.0"
    assert data["request"]["workflow_url"] == "./Dockstore.cwl"
    assert data["run_id"] == run_id
    assert data["run_log"]["exit_code"] == 0
    assert data["run_log"]["name"] is None
    assert str(data["state"]) == "COMPLETE"
    assert data["task_logs"] is None
