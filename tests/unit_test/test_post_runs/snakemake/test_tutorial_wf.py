#!/usr/bin/env python3
# coding: utf-8
import json
import shlex
import subprocess
from time import sleep

from sapporo.type import RunId

from . import SCRIPT_DIR, TEST_HOST, TEST_PORT  # type: ignore


def post_runs_tutorial_wf() -> RunId:
    script_path = \
        SCRIPT_DIR.joinpath("tutorial_wf/post_runs.sh")
    proc = subprocess.run(shlex.split(f"/bin/bash {str(script_path)}"),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          encoding="utf-8",
                          env={"SAPPORO_HOST": TEST_HOST,
                               "SAPPORO_PORT": TEST_PORT})

    assert proc.returncode == 0
    res_data: RunId = json.loads(proc.stdout)

    return res_data


def test_tutorial_wf(setup_test_server: None) -> None:
    res_data = post_runs_tutorial_wf()
    assert "run_id" in res_data
    run_id = res_data["run_id"]

    from .. import get_run_id_status
    count = 0
    while count <= 600:
        get_status_data = get_run_id_status(run_id)
        if str(get_status_data["state"]) == "COMPLETE":
            break
        sleep(1)
        count += 1
    assert str(get_status_data["state"]) == "COMPLETE"

    from .. import get_run_id
    data = get_run_id(run_id)

    assert "calls/all.vcf" in data["outputs"]
    assert "mapped/A.sorted.bam" in data["outputs"]
    assert "mapped/B.sorted.bam" in data["outputs"]
    assert "plots/quals.svg" in data["outputs"]
    assert "{}" == data["request"]["tags"]
    assert len(data["request"]["workflow_attachment"]) == 15
    assert "snakemake" == data["request"]["workflow_engine_name"]
    assert "{\n  \"--cores\": \"1\",\n  \"--use-conda\": \"\"\n}\n" == \
        data["request"]["workflow_engine_parameters"]
    assert "Snakefile" == data["request"]["workflow_name"]
    assert "Snakemake" == data["request"]["workflow_type"]
    assert "v1.0" == data["request"]["workflow_type_version"]
    assert "./Snakefile" == data["request"]["workflow_url"]
    assert run_id == data["run_id"]
    assert data["run_log"]["exit_code"] == 0
    assert data["run_log"]["name"] == "Snakefile"
    assert "Finished job 0." in data["run_log"]["stderr"]
    assert str(data["state"]) == "COMPLETE"
    assert data["task_logs"] is None
