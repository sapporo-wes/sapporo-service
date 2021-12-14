#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=unused-argument, import-outside-toplevel, subprocess-run-check
import json
import shlex
import subprocess
from time import sleep
from typing import cast

from flask.testing import FlaskClient
from sapporo.model import RunId, RunRequest

from . import RESOURCE, SCRIPT_DIR, TEST_HOST, TEST_PORT


def post_runs_attach_all_files_with_flask(client: FlaskClient) -> RunId:
    with SCRIPT_DIR.joinpath(
            "attach_all_files/workflow_params.json").open(mode="r") as f:
        workflow_params = f.read()
    data: RunRequest = {  # type: ignore
        "workflow_params": workflow_params,
        "workflow_type": "CWL",
        "workflow_type_version": "v1.0",
        "workflow_url": RESOURCE["WF"].name,
        "workflow_engine_name": "cwltool",
    }
    data["workflow_attachment[]"] = [  # type: ignore
        (RESOURCE["FQ_1"].open(mode="rb"), RESOURCE["FQ_1"].name),
        (RESOURCE["FQ_2"].open(mode="rb"), RESOURCE["FQ_2"].name),
        (RESOURCE["WF"].open(mode="rb"), RESOURCE["WF"].name),
        (RESOURCE["TOOL_1"].open(mode="rb"), RESOURCE["TOOL_1"].name),
        (RESOURCE["TOOL_2"].open(mode="rb"), RESOURCE["TOOL_2"].name)
    ]
    res = client.post("/runs", data=data, content_type="multipart/form-data")

    assert res.status_code == 200
    res_data = cast(RunId, res.get_json())

    return res_data


def post_runs_attach_all_files() -> RunId:
    script_path = SCRIPT_DIR.joinpath("attach_all_files/post_runs.sh")
    proc = subprocess.run(shlex.split(f"/bin/bash {str(script_path)}"),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          encoding="utf-8",
                          env={"SAPPORO_HOST": TEST_HOST,
                               "SAPPORO_PORT": TEST_PORT})
    assert proc.returncode == 0
    res_data: RunId = json.loads(proc.stdout)

    return res_data


def test_attach_all_files(setup_test_server: None) -> None:
    res_data = post_runs_attach_all_files()
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
    assert len(wf_attachment) == 5
    assert data["request"]["workflow_engine_name"] == "cwltool"
    assert data["request"]["workflow_engine_parameters"] is None
    assert data["request"]["workflow_name"] is None
    assert data["request"]["workflow_type"] == "CWL"
    assert data["request"]["workflow_type_version"] == "v1.0"
    assert data["request"]["workflow_url"] == "./trimming_and_qc.cwl"
    assert data["run_id"] == run_id
    assert data["run_log"]["exit_code"] == 0
    assert data["run_log"]["name"] is None
    assert "Final process status is success" in data["run_log"]["stderr"]
    assert str(data["state"]) == "COMPLETE"
    assert data["task_logs"] is None
