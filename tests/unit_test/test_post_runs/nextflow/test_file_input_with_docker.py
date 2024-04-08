# coding: utf-8
# pylint: disable=unused-argument, import-outside-toplevel, subprocess-run-check
import json
from pathlib import Path
from typing import Dict

from flask.testing import FlaskClient

from .conftest import wait_for_run_to_complete


def test_file_input_with_docker(delete_env_vars: None, test_client: FlaskClient, resources: Dict[str, Path]) -> None:  # type: ignore
    res = test_client.post("/runs", data={
        "workflow_params": json.dumps({
            "input_file": f"./{resources['NF_TEST_INPUT'].name}"
        }),
        "workflow_type": "NFL",
        "workflow_type_version": "1.0",
        "workflow_url": f"./{resources['FILE_INPUT'].name}",
        "workflow_engine": "nextflow",
        "workflow_engine_parameters": json.dumps({
            "-with-docker": "ubuntu:20.04",
            "-dsl1": ""
        }),
        "workflow_attachment": [
            (resources["FILE_INPUT"].open(mode="rb"), resources["FILE_INPUT"].name),
            (resources["NF_TEST_INPUT"].open(mode="rb"), resources["NF_TEST_INPUT"].name),
        ],
    }, content_type="multipart/form-data")
    res_data = res.get_json()
    assert "run_id" in res_data
    run_id = res_data["run_id"]

    wait_for_run_to_complete(test_client, run_id)

    res = test_client.get(f"/runs/{run_id}")
    res_data = res.get_json()

    assert res_data["request"]["workflow_engine_parameters"] == json.dumps({
        "-with-docker": "ubuntu:20.04",
        "-dsl1": ""
    })
    assert res_data["state"] == "COMPLETE"
