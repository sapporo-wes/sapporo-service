#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=unused-argument, import-outside-toplevel, subprocess-run-check
import json
import shlex
import subprocess
from time import sleep

from sapporo.model import RunId

from . import RESOURCE_REMOTE, SCRIPT_DIR, TEST_HOST, TEST_PORT


def post_runs_registered_workflow() -> RunId:
    script_path = \
        SCRIPT_DIR.joinpath("registered_workflow/post_runs.sh")
    proc = subprocess.run(shlex.split(f"/bin/bash {str(script_path)}"),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          encoding="utf-8",
                          env={"SAPPORO_HOST": TEST_HOST,
                               "SAPPORO_PORT": TEST_PORT})
    assert proc.returncode == 0
    res_data: RunId = json.loads(proc.stdout)

    return res_data


def test_registered_workflow(setup_test_server: None) -> None:
    res_data = post_runs_registered_workflow()
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

    assert len(data["outputs"]) == 6
    assert data["request"]["tags"] is None
    wf_attachment = \
        json.loads(data["request"]["workflow_attachment"])  # type: ignore
    assert len(wf_attachment) == 2
    assert data["request"]["workflow_engine_name"] == "cwltool"
    assert data["request"]["workflow_engine_parameters"] is None
    assert data["request"]["workflow_name"] == "Example workflow - CWL - Trimming and QC"
    assert data["request"]["workflow_type"] == "CWL"
    assert data["request"]["workflow_type_version"] == "v1.0"
    assert data["request"]["workflow_url"] == RESOURCE_REMOTE["WF"]
    assert data["run_id"] == run_id
    assert data["run_log"]["exit_code"] == 0
    assert data["run_log"]["name"] == "Example workflow - CWL - Trimming and QC"
    assert "status is success" in data["run_log"]["stderr"]  # type: ignore
    assert str(data["state"]) == "COMPLETE"
    assert data["task_logs"] is None
