# coding: utf-8
# pylint: disable=unused-argument, import-outside-toplevel, subprocess-run-check
import json
from pathlib import Path
from typing import Dict

from flask.testing import FlaskClient

from .conftest import wait_for_run_to_complete


def test_bamstats_wdl(delete_env_vars: None, test_client: FlaskClient, resources: Dict[str, Path]) -> None:  # type: ignore
    res = test_client.post("/runs", data={
        "workflow_params": resources["WDL_PARAMS"].read_text(),
        "workflow_type": "WDL",
        "workflow_type_version": "1.0",
        "workflow_url": f"./{resources['WDL_WF'].name}",
        "workflow_engine_name": "cromwell",
        "tags": json.dumps({
            "workflow_name": "dockstore-tool-bamstats-wdl"
        }),
        "workflow_attachment": [
            (resources["WDL_WF"].open(mode="rb"), resources["WDL_WF"].name),
            (resources["DATA"].open(mode="rb"), resources["DATA"].name)
        ],
    }, content_type="multipart/form-data")
    res_data = res.get_json()
    assert "run_id" in res_data
    run_id = res_data["run_id"]

    wait_for_run_to_complete(test_client, run_id)

    res = test_client.get(f"/runs/{run_id}")
    res_data = res.get_json()

    assert len(res_data["outputs"]) == 1
    assert len(json.loads(res_data["request"]["workflow_attachment"])) == 2
    assert res_data["request"]["workflow_engine_name"] == "cromwell"
    assert res_data["request"]["workflow_engine_parameters"] is None
    assert res_data["request"]["workflow_name"] is None
    assert res_data["request"]["workflow_type"] == "WDL"
    assert res_data["request"]["workflow_type_version"] == "1.0"
    assert res_data["request"]["workflow_url"] == f"./{resources['WDL_WF'].name}"
    assert res_data["run_id"] == run_id
    assert res_data["run_log"]["exit_code"] == 0
    assert res_data["run_log"]["name"] is None
    assert "Workflow bamstatsWorkflow complete." in res_data["run_log"]["stdout"]
    assert str(res_data["state"]) == "COMPLETE"
    assert res_data["task_logs"] is None
