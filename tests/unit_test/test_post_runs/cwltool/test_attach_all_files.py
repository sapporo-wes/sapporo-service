# coding: utf-8
# pylint: disable=unused-argument, import-outside-toplevel, subprocess-run-check
import json
from pathlib import Path
from typing import Dict

from flask.testing import FlaskClient

from .conftest import wait_for_run_to_complete


def test_attach_all_files(delete_env_vars: None, test_client: FlaskClient, resources: Dict[str, Path]) -> None:  # type: ignore
    res = test_client.post("/runs", data={
        "workflow_params": json.dumps({
            "fastq_1": {
                "class": "File",
                "path": resources["FQ_1"].name,
            },
            "fastq_2": {
                "class": "File",
                "path": resources["FQ_2"].name,
            }}),
        "workflow_type": "CWL",
        "workflow_type_version": "v1.0",
        "workflow_url": resources["WF"].name,
        "workflow_engine_name": "cwltool",
        "workflow_attachment": [
            (resources["FQ_1"].open(mode="rb"), resources["FQ_1"].name),
            (resources["FQ_2"].open(mode="rb"), resources["FQ_2"].name),
            (resources["WF"].open(mode="rb"), resources["WF"].name),
            (resources["TOOL_1"].open(mode="rb"), resources["TOOL_1"].name),
            (resources["TOOL_2"].open(mode="rb"), resources["TOOL_2"].name)
        ]
    }, content_type="multipart/form-data")
    res_data = res.get_json()
    assert "run_id" in res_data
    run_id = res_data["run_id"]

    wait_for_run_to_complete(test_client, run_id)

    res = test_client.get(f"/runs/{run_id}")
    res_data = res.get_json()

    assert len(res_data["outputs"]) == 6
    assert len(json.loads(res_data["request"]["workflow_attachment"])) == 5
    assert res_data["request"]["workflow_engine_name"] == "cwltool"
    assert res_data["request"]["workflow_engine_parameters"] is None
    assert res_data["request"]["workflow_name"] is None
    assert res_data["request"]["workflow_type"] == "CWL"
    assert res_data["request"]["workflow_type_version"] == "v1.0"
    assert res_data["request"]["workflow_url"] == resources["WF"].name
    assert res_data["run_id"] == run_id
    assert res_data["run_log"]["exit_code"] == 0
    assert res_data["run_log"]["name"] is None
    assert "Final process status is success" in res_data["run_log"]["stderr"]
    assert str(res_data["state"]) == "COMPLETE"
    assert res_data["task_logs"] is None
