# coding: utf-8
# pylint: disable=unused-argument, import-outside-toplevel, subprocess-run-check
import json
from pathlib import Path
from typing import Dict

from flask.testing import FlaskClient

from .conftest import RESOURCE_DIR, wait_for_run_to_complete


def test_tutorial_wf(delete_env_vars: None, test_client: FlaskClient, resources: Dict[str, Path]) -> None:  # type: ignore
    res = test_client.post("/runs", data={
        "workflow_params": json.dumps({}),
        "workflow_type": "SMK",
        "workflow_type_version": "1.0",
        "workflow_url": f"./{resources['WORKFLOW'].name}",
        "workflow_engine_name": "snakemake",
        "workflow_engine_parameters": json.dumps({
            "--cores": "1",
            "--use-conda": ""
        }),
        "workflow_attachment": [(file.open(mode="rb"), str(file.relative_to(RESOURCE_DIR))) for file in resources.values()]
    }, content_type="multipart/form-data")
    res_data = res.get_json()
    assert "run_id" in res_data
    run_id = res_data["run_id"]

    wait_for_run_to_complete(test_client, run_id)

    res = test_client.get(f"/runs/{run_id}")
    res_data = res.get_json()

    from pprint import pprint
    pprint(res_data)

    assert len(res_data["outputs"]) == 3
    assert len(json.loads(res_data["request"]["workflow_attachment"])) == 15
    assert res_data["request"]["workflow_engine_name"] == "snakemake"
    assert res_data["request"]["workflow_engine_parameters"] == json.dumps({"--cores": "1", "--use-conda": ""})
    assert res_data["request"]["workflow_name"] is None
    assert res_data["request"]["workflow_type"] == "SMK"
    assert res_data["request"]["workflow_type_version"] == "1.0"
    assert res_data["request"]["workflow_url"] == f"./{resources['WORKFLOW'].name}"
    assert res_data["run_id"] == run_id
    assert res_data["run_log"]["exit_code"] == 0
    assert res_data["run_log"]["name"] is None
    assert "Finished job 0." in res_data["run_log"]["stderr"]
    assert str(res_data["state"]) == "COMPLETE"
    assert res_data["task_logs"] is None
