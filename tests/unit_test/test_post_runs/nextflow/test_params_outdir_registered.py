#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=subprocess-run-check, unused-argument, import-outside-toplevel
import json
import shlex
import subprocess
from time import sleep

from sapporo.model import RunId

from . import SCRIPT_DIR, TEST_HOST, TEST_PORT


def post_runs_params_outdir_registered() -> RunId:
    script_path = SCRIPT_DIR.joinpath("params_outdir_registered/post_runs.sh")
    proc = subprocess.run(shlex.split(f"/bin/bash {str(script_path)}"),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          encoding="utf-8",
                          env={"SAPPORO_HOST": TEST_HOST,
                               "SAPPORO_PORT": TEST_PORT})
    assert proc.returncode == 0
    res_data: RunId = json.loads(proc.stdout)

    return res_data


def test_params_outdir_registered(setup_test_server: None) -> None:
    res_data = post_runs_params_outdir_registered()
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

    assert data["request"]["tags"] is None
    wf_attachment = \
        json.loads(data["request"]["workflow_attachment"])  # type: ignore
    assert any("params_outdir.nf" in obj["file_name"] for obj in wf_attachment)
    assert data["request"]["workflow_engine_name"] == "nextflow"
    assert data["request"]["workflow_engine_parameters"] is None
    assert data["request"]["workflow_name"] == "nextflow_params_outdir"
    assert data["request"]["workflow_params"] == \
        "{\n  \"str\": \"sapporo-nextflow-params_outdir\",\n  \"outdir\": \"\"\n}\n"
    assert data["request"]["workflow_type"] == "NFL"
    assert data["request"]["workflow_type_version"] == "1.0"
    assert data["request"]["workflow_url"] == "./params_outdir.nf"
    assert data["run_id"] == run_id
    assert data["run_log"]["exit_code"] == 0
    assert data["run_log"]["name"] == "nextflow_params_outdir"
    assert "[100%] 1 of 1" in data["run_log"]["stdout"]  # type: ignore
    assert str(data["state"]) == "COMPLETE"
    assert data["task_logs"] is None
