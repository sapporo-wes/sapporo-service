# coding: utf-8
from pathlib import Path
from time import sleep
from typing import Dict

import pytest
from flask.testing import FlaskClient

PACKAGE_ROOT = Path(__file__).parent
while not PACKAGE_ROOT.joinpath("setup.py").exists():
    if PACKAGE_ROOT == PACKAGE_ROOT.parent:
        raise FileNotFoundError('setup.py not found in any parent directories.')
    PACKAGE_ROOT = PACKAGE_ROOT.parent


RESOURCE_DIR = PACKAGE_ROOT.joinpath("tests/resources/cwltool").resolve()
REMOTE_URL = "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/"


@pytest.fixture()
def resources() -> Dict[str, Path]:
    return {
        "FQ_1": RESOURCE_DIR.joinpath("ERR034597_1.small.fq.gz"),
        "FQ_2": RESOURCE_DIR.joinpath("ERR034597_2.small.fq.gz"),
        "WF": RESOURCE_DIR.joinpath("trimming_and_qc.cwl"),
        "WF_PACKED": RESOURCE_DIR.joinpath("trimming_and_qc_packed.cwl"),
        "WF_REMOTE": RESOURCE_DIR.joinpath("trimming_and_qc_remote.cwl"),
        "TOOL_1": RESOURCE_DIR.joinpath("fastqc.cwl"),
        "TOOL_2": RESOURCE_DIR.joinpath("trimmomatic_pe.cwl"),
    }


@pytest.fixture()
def remote_resources() -> Dict[str, str]:
    return {
        "FQ_1": REMOTE_URL + "ERR034597_1.small.fq.gz",
        "FQ_2": REMOTE_URL + "ERR034597_2.small.fq.gz",
        "WF": REMOTE_URL + "trimming_and_qc.cwl",
        "WF_PACKED": REMOTE_URL + "trimming_and_qc_packed.cwl",
        "WF_REMOTE": REMOTE_URL + "trimming_and_qc_remote.cwl",
        "TOOL_1": REMOTE_URL + "fastqc.cwl",
        "TOOL_2": REMOTE_URL + "trimmomatic_pe.cwl",
    }


def wait_for_run_to_complete(client: FlaskClient, run_id: str) -> None:  # type: ignore
    count = 0
    while count <= 120:
        sleep(3)
        res = client.get(f"/runs/{run_id}")
        res_data = res.get_json()
        if res_data["state"] in ["COMPLETE", "EXECUTOR_ERROR", "SYSTEM_ERROR", "CANCELED"]:
            break
        count += 1
    if count > 120:
        raise TimeoutError(f"Run {run_id} did not complete in time.")
    if res_data["state"] != "COMPLETE":
        client.get(f"/runs/{run_id}")
        res_data = res.get_json()
        import json
        print(json.dumps(res_data, indent=2))
        raise RuntimeError(f"Run {run_id} failed with state {res_data['state']}.")
