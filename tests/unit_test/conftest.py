# coding: utf-8
# pylint: disable=redefined-outer-name, unused-argument
import json
import os
import shutil
import tempfile
from pathlib import Path
from time import sleep
from typing import Dict, Generator

import pkg_resources
import pytest
from flask.testing import FlaskClient
from pytest import MonkeyPatch

from sapporo.app import create_app
from sapporo.config import Config

PACKAGE_ROOT = Path(__file__).parent
while not PACKAGE_ROOT.joinpath("setup.py").exists():
    if PACKAGE_ROOT == PACKAGE_ROOT.parent:
        raise FileNotFoundError('setup.py not found in any parent directories.')
    PACKAGE_ROOT = PACKAGE_ROOT.parent


@pytest.fixture()
def tmpdir() -> Generator[Path, None, None]:
    tempdir = tempfile.mkdtemp()
    yield Path(tempdir)
    try:
        shutil.rmtree(tempdir)
    except PermissionError:
        pass


@pytest.fixture
def delete_env_vars(monkeypatch: MonkeyPatch) -> Generator[None, None, None]:
    sapporo_envs: Dict[str, str] = {key: value for key, value in os.environ.items() if key.startswith("SAPPORO")}

    for key in sapporo_envs:
        monkeypatch.delenv(key, raising=False)

    yield  # execute the test function

    # restore the original environment variables after the test function
    for key, value in sapporo_envs.items():
        monkeypatch.setenv(key, value)


def get_default_config(tmpdir: Path) -> Config:
    config: Config = {
        "host": "localhost",
        "port": 8888,
        "debug": True,
        "run_dir": tmpdir,
        "sapporo_version": pkg_resources.get_distribution("sapporo").version,
        "get_runs": True,
        "workflow_attachment": True,
        "registered_only_mode": False,
        "service_info": PACKAGE_ROOT.joinpath("sapporo/service-info.json").resolve(),
        "executable_workflows": PACKAGE_ROOT.joinpath("sapporo/executable_workflows.json").resolve(),
        "run_sh": PACKAGE_ROOT.joinpath("sapporo/run.sh").resolve(),
        "url_prefix": "",
        "access_control_allow_origin": "*",
    }
    return config


@pytest.fixture()
def default_config(tmpdir: Path) -> Config:
    return get_default_config(tmpdir)


def setup_test_client(config: Config) -> FlaskClient:  # type: ignore
    app = create_app(config)
    client = app.test_client()
    return client


@pytest.fixture()
def test_client(default_config: Config, tmpdir: Path) -> Generator[FlaskClient, None, None]:  # type: ignore
    yield setup_test_client(default_config)


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
        print(json.dumps(res_data, indent=2))
        raise RuntimeError(f"Run {run_id} failed with state {res_data['state']}.")


def run_workflow(client: FlaskClient) -> str:  # type: ignore
    REMOTE_URL = "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/"
    res = client.post("/runs", data={
        "workflow_params": json.dumps({
            "fastq_1": {
                "class": "File",
                "path": REMOTE_URL + "ERR034597_1.small.fq.gz",
            },
            "fastq_2": {
                "class": "File",
                "path": REMOTE_URL + "ERR034597_2.small.fq.gz",
            }}),
        "workflow_type": "CWL",
        "workflow_type_version": "v1.0",
        "workflow_url": REMOTE_URL + "trimming_and_qc.cwl",
        "workflow_engine_name": "cwltool",
    }, content_type="multipart/form-data")

    res_data = res.get_json()
    assert "run_id" in res_data
    run_id: str = res_data["run_id"]

    return run_id
