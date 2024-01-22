
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


RESOURCE_DIR = PACKAGE_ROOT.joinpath("tests/resources/nextflow").resolve()
REMOTE_URL = "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/nextflow/"


@pytest.fixture()
def resources() -> Dict[str, Path]:
    return {
        "FILE_INPUT": RESOURCE_DIR.joinpath("file_input.nf"),
        "NF_TEST_INPUT": RESOURCE_DIR.joinpath("nf_test_input.txt"),
        "PARAMS_OUTDIR": RESOURCE_DIR.joinpath("params_outdir.nf"),
        "STR_INPUT": RESOURCE_DIR.joinpath("str_input.nf")
    }


@pytest.fixture()
def remote_resources() -> Dict[str, str]:
    return {
        "FILE_INPUT": REMOTE_URL + "file_input.nf",
        "NF_TEST_INPUT": REMOTE_URL + "nf_test_input.txt",
        "PARAMS_OUTDIR": REMOTE_URL + "params_outdir.nf",
        "STR_INPUT": REMOTE_URL + "str_input.nf"
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
