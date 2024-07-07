# pylint: disable=C0415, W0613, W0621

import json

from .conftest import (anyhow_get_test_client, assert_run_complete,
                       package_root, post_run, wait_for_run)

RESOURCE_BASE_PATH = package_root().joinpath("tests/resources/nextflow")


def test_run_nextflow_str_input(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **{
        "workflow_type": "NFL",
        "workflow_engine": "nextflow",
        "workflow_params": json.dumps({"str": "some_string"}),
        "workflow_url": "str_input.nf",
        "workflow_engine_parameters": json.dumps({
            "-with-docker": "ubuntu:20.04",
            "-dsl1": "",
        }),
        "workflow_attachment": [
            ("workflow_attachment", ("str_input.nf", open(RESOURCE_BASE_PATH.joinpath("str_input.nf"), "rb"))),
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


def test_run_nextflow_file_input(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **{
        "workflow_type": "NFL",
        "workflow_engine": "nextflow",
        "workflow_params": json.dumps({"input_file": "./nf_test_input.txt"}),
        "workflow_url": "file_input.nf",
        "workflow_engine_parameters": json.dumps({
            "-with-docker": "ubuntu:20.04",
            "-dsl1": "",
        }),
        "workflow_attachment": [
            ("workflow_attachment", ("file_input.nf", open(RESOURCE_BASE_PATH.joinpath("file_input.nf"), "rb"))),
            ("workflow_attachment", ("nf_test_input.txt", open(RESOURCE_BASE_PATH.joinpath("nf_test_input.txt"), "rb"))),
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


def test_run_nextflow_params_outdir(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **{
        "workflow_type": "NFL",
        "workflow_engine": "nextflow",
        "workflow_params": json.dumps({
            "str": "sapporo-nextflow-params_outdir",
            "outdir": "",
        }),
        "workflow_url": "params_outdir.nf",
        "workflow_engine_parameters": json.dumps({
            "-with-docker": "ubuntu:20.04",
            "-dsl1": "",
        }),
        "workflow_attachment": [
            ("workflow_attachment", ("params_outdir.nf", open(RESOURCE_BASE_PATH.joinpath("params_outdir.nf"), "rb"))),
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
