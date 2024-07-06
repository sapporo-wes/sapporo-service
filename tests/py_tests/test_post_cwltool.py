# pylint: disable=C0415, W0613, W0621
import json
from pathlib import Path

from .conftest import anyhow_get_test_client, post_run, wait_for_run_complete

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
    response = post_run(client, **remote_wf_run_request)  # type: ignore
    assert response.status_code == 200
    data = response.json()

    return data["run_id"]


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

    # Individual assertions
    assert data["run_id"] == run_id
    assert data["state"] == "COMPLETE"
    assert data["run_log"]["name"] is None
    assert data["run_log"]["cmd"] is not None
    assert data["run_log"]["start_time"] is not None
    assert data["run_log"]["end_time"] is not None
    assert data["run_log"]["stdout"] is not None
    assert data["run_log"]["stderr"] is not None
    assert data["run_log"]["exit_code"] == 0
    assert data["run_log"]["system_logs"] == []
    assert data["task_logs_url"] is None
    assert data["task_logs"] is None
    assert len(data["outputs"]) == 6


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

    # Individual assertions
    assert "run_id" in data
    assert data["run_id"] == run_id
    assert data["state"] == "COMPLETE"
    assert data["run_log"]["name"] is None
    assert data["run_log"]["cmd"] is not None
    assert data["run_log"]["start_time"] is not None
    assert data["run_log"]["end_time"] is not None
    assert data["run_log"]["stdout"] is not None
    assert data["run_log"]["stderr"] is not None
    assert data["run_log"]["exit_code"] == 0
    assert data["run_log"]["system_logs"] == []
    assert data["task_logs_url"] is None
    assert data["task_logs"] is None
    assert len(data["outputs"]) == 6
