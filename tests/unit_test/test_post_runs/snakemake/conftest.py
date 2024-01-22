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


RESOURCE_DIR = PACKAGE_ROOT.joinpath("tests/resources/snakemake").resolve()


@pytest.fixture()
def resources() -> Dict[str, Path]:
    return {
        "WORKFLOW": RESOURCE_DIR.joinpath("Snakefile"),
        "SCRIPT_1": RESOURCE_DIR.joinpath("scripts/plot-quals.py"),
        "ENV_1": RESOURCE_DIR.joinpath("envs/stats.yaml"),
        "ENV_2": RESOURCE_DIR.joinpath("envs/calling.yaml"),
        "ENV_3": RESOURCE_DIR.joinpath("envs/mapping.yaml"),
        "SAMPLE_1": RESOURCE_DIR.joinpath("data/samples/A.fastq"),
        "SAMPLE_2": RESOURCE_DIR.joinpath("data/samples/B.fastq"),
        "SAMPLE_3": RESOURCE_DIR.joinpath("data/samples/C.fastq"),
        "SAMPLE_4": RESOURCE_DIR.joinpath("data/genome.fa"),
        "SAMPLE_5": RESOURCE_DIR.joinpath("data/genome.fa.amb"),
        "SAMPLE_6": RESOURCE_DIR.joinpath("data/genome.fa.fai"),
        "SAMPLE_7": RESOURCE_DIR.joinpath("data/genome.fa.sa"),
        "SAMPLE_8": RESOURCE_DIR.joinpath("data/genome.fa.pac"),
        "SAMPLE_9": RESOURCE_DIR.joinpath("data/genome.fa.ann"),
        "SAMPLE_10": RESOURCE_DIR.joinpath("data/genome.fa.bwt")
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
