# coding: utf-8
# pylint: disable=unused-argument, import-outside-toplevel, subprocess-run-check
import json
from pathlib import Path
from typing import Dict

from flask.testing import FlaskClient

from .conftest import wait_for_run_to_complete


def test_params_outdir(delete_env_vars: None, test_client: FlaskClient, resources: Dict[str, Path]) -> None:  # type: ignore
    res = test_client.post("/runs", data={
        "workflow_params": json.dumps({
            "str": "sapporo-nextflow-params_outdir",
            "outdir": "",
        }),
        "workflow_type": "NFL",
        "workflow_type_version": "1.0",
        "workflow_url": f"./{resources['PARAMS_OUTDIR'].name}",
        "workflow_engine_name": "nextflow",
        "workflow_attachment": [
            (resources["PARAMS_OUTDIR"].open(mode="rb"), resources["PARAMS_OUTDIR"].name),
        ],
    }, content_type="multipart/form-data")
    res_data = res.get_json()
    assert "run_id" in res_data
    run_id = res_data["run_id"]

    wait_for_run_to_complete(test_client, run_id)

    res = test_client.get(f"/runs/{run_id}")
    res_data = res.get_json()

    assert res_data["state"] == "COMPLETE"
