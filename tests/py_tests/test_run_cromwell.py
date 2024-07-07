# pylint: disable=C0415, W0613, W0621

from .conftest import (anyhow_get_test_client, assert_run_complete,
                       package_root, post_run, wait_for_run)

RESOURCE_BASE_PATH = package_root().joinpath("tests/resources/cromwell/dockstore-tool-bamstats")


def test_run_cromwell_bamstats_cwl(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **{
        "workflow_type": "CWL",
        "workflow_engine": "cromwell",
        "workflow_params": RESOURCE_BASE_PATH.joinpath("test.json").read_text(encoding="utf-8"),
        "workflow_url": "Dockstore.cwl",
        "workflow_attachment": [
            ("workflow_attachment", ("Dockstore.cwl", open(RESOURCE_BASE_PATH.joinpath("Dockstore.cwl"), "rb"))),
            ("workflow_attachment", ("tiny.bam", open(RESOURCE_BASE_PATH.joinpath("tiny.bam"), "rb"))),
        ]
    })  # type: ignore
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    state = wait_for_run(client, run_id)
    assert state == "COMPLETE"

    response = client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()

    assert_run_complete(run_id, data)
    assert len(data["outputs"]) != 0


def test_run_cromwell_bamstats_wdl(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **{
        "workflow_type": "WDL",
        "workflow_engine": "cromwell",
        "workflow_params": RESOURCE_BASE_PATH.joinpath("test.wdl.json").read_text(encoding="utf-8"),
        "workflow_url": "Dockstore.wdl",
        "workflow_attachment": [
            ("workflow_attachment", ("Dockstore.wdl", open(RESOURCE_BASE_PATH.joinpath("Dockstore.wdl"), "rb"))),
            ("workflow_attachment", ("tiny.bam", open(RESOURCE_BASE_PATH.joinpath("tiny.bam"), "rb"))),
        ]
    })  # type: ignore
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    state = wait_for_run(client, run_id)
    assert state == "COMPLETE"

    response = client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()

    assert_run_complete(run_id, data)
    assert len(data["outputs"]) != 0
