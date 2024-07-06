# pylint: disable=C0415, W0613, W0621

import json
from pathlib import Path

from .conftest import (anyhow_get_test_client, assert_run_complete, post_run,
                       wait_for_run_complete)

REMOTE_BASE_URL = "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/"


remote_wf_run_request = {
    "workflow_type": "CWL",
    "workflow_engine": "cwltool",
    "workflow_params": json.dumps({
        "fastq_1": {"class": "File", "path": f"{REMOTE_BASE_URL}ERR034597_1.small.fq.gz"},
        "fastq_2": {"class": "File", "path": f"{REMOTE_BASE_URL}ERR034597_2.small.fq.gz"},
    }),
    "workflow_url": f"{REMOTE_BASE_URL}trimming_and_qc.cwl",
}


def post_run_cwltool_remote_wf(client):  # type: ignore
    """\
    For other test functions to use.
    """
    response = post_run(client, **remote_wf_run_request)  # type: ignore
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    wait_for_run_complete(client, run_id)

    return run_id


def test_post_run_cwltool_remote_wf(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **remote_wf_run_request)  # type: ignore

    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    run_id = data["run_id"]

    wait_for_run_complete(client, run_id)

    response = client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()

    assert_run_complete(run_id, data)


RESOURCE_BASE_PATH = Path(__file__).parent.parent.joinpath("resources/cwltool")


attach_all_run_request = {
    "workflow_type": "CWL",
    "workflow_engine": "cwltool",
    "workflow_params": json.dumps({
        "fastq_1": {"class": "File", "path": "ERR034597_1.small.fq.gz"},
        "fastq_2": {"class": "File", "path": "ERR034597_2.small.fq.gz"},
    }),
    "workflow_url": "trimming_and_qc.cwl",
    "workflow_attachment": [
        ("workflow_attachment", ("ERR034597_1.small.fq.gz", open(RESOURCE_BASE_PATH.joinpath("ERR034597_1.small.fq.gz"), "rb"))),
        ("workflow_attachment", ("ERR034597_2.small.fq.gz", open(RESOURCE_BASE_PATH.joinpath("ERR034597_2.small.fq.gz"), "rb"))),
        ("workflow_attachment", ("trimming_and_qc.cwl", open(RESOURCE_BASE_PATH.joinpath("trimming_and_qc.cwl"), "rb"))),
        ("workflow_attachment", ("trimmomatic_pe.cwl", open(RESOURCE_BASE_PATH.joinpath("trimmomatic_pe.cwl"), "rb"))),
        ("workflow_attachment", ("fastqc.cwl", open(RESOURCE_BASE_PATH.joinpath("fastqc.cwl"), "rb"))),
    ]
}


def test_post_run_cwltool_attach_all_files(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **attach_all_run_request)  # type: ignore
    data = response.json()

    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    run_id = data["run_id"]

    wait_for_run_complete(client, run_id)

    response = client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()

    assert_run_complete(run_id, data)
