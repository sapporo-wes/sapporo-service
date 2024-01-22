# coding: utf-8
# pylint: disable=unused-argument, import-outside-toplevel, subprocess-run-check
import json
from typing import Dict

from flask.testing import FlaskClient

from .conftest import wait_for_run_to_complete


def test_registered_workflow(delete_env_vars: None, test_client: FlaskClient, remote_resources: Dict[str, str]) -> None:  # type: ignore
    res = test_client.post("/runs", data={
        "workflow_name": "Example workflow - CWL - Trimming and QC",
        "workflow_params": json.dumps({
            "fastq_1": {
                "class": "File",
                "location": remote_resources["FQ_1"]
            },
            "fastq_2": {
                "class": "File",
                "location": remote_resources["FQ_2"]
            }}),
        "workflow_engine_name": "cwltool",
    }, content_type="multipart/form-data")
    res_data = res.get_json()
    assert "run_id" in res_data
    run_id = res_data["run_id"]

    wait_for_run_to_complete(test_client, run_id)

    res = test_client.get(f"/runs/{run_id}")
    res_data = res.get_json()

    assert len(res_data["outputs"]) == 6
    assert len(json.loads(res_data["request"]["workflow_attachment"])) == 2
    assert res_data["request"]["workflow_engine_name"] == "cwltool"
    assert res_data["request"]["workflow_engine_parameters"] is None
    assert res_data["request"]["workflow_name"] == "Example workflow - CWL - Trimming and QC"
    assert res_data["request"]["workflow_type"] == "CWL"
    assert res_data["request"]["workflow_type_version"] == "v1.0"
    assert res_data["request"]["workflow_url"] == remote_resources["WF"]
    assert res_data["run_id"] == run_id
    assert res_data["run_log"]["exit_code"] == 0
    assert res_data["run_log"]["name"] == "Example workflow - CWL - Trimming and QC"
    assert "status is success" in res_data["run_log"]["stderr"]
    assert res_data["state"] == "COMPLETE"
    assert res_data["task_logs"] is None
