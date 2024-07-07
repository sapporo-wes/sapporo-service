# pylint: disable=C0415, W0613, W0621

import json

from .conftest import (anyhow_get_test_client, assert_run_complete,
                       package_root, post_run, wait_for_run)

RESOURCE_BASE_PATH = package_root().joinpath("tests/resources/snakemake")


def test_run_snakemake(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **{
        "workflow_type": "SMK",
        "workflow_engine": "snakemake",
        "workflow_params": json.dumps({}),
        "workflow_url": "Snakefile",
        "workflow_engine_parameters": json.dumps({
            "--cores": "1",
            "--use-conda": "",
        }),
        "workflow_attachment": [
            ("workflow_attachment", ("Snakefile", open(RESOURCE_BASE_PATH.joinpath("Snakefile"), "rb"))),
            ("workflow_attachment", ("scripts/plot-quals.py", open(RESOURCE_BASE_PATH.joinpath("scripts/plot-quals.py"), "rb"))),
            ("workflow_attachment", ("envs/stats.yaml", open(RESOURCE_BASE_PATH.joinpath("envs/stats.yaml"), "rb"))),
            ("workflow_attachment", ("envs/calling.yaml", open(RESOURCE_BASE_PATH.joinpath("envs/calling.yaml"), "rb"))),
            ("workflow_attachment", ("envs/mapping.yaml", open(RESOURCE_BASE_PATH.joinpath("envs/mapping.yaml"), "rb"))),
            ("workflow_attachment", ("data/samples/A.fastq", open(RESOURCE_BASE_PATH.joinpath("data/samples/A.fastq"), "rb"))),
            ("workflow_attachment", ("data/samples/B.fastq", open(RESOURCE_BASE_PATH.joinpath("data/samples/B.fastq"), "rb"))),
            ("workflow_attachment", ("data/samples/C.fastq", open(RESOURCE_BASE_PATH.joinpath("data/samples/C.fastq"), "rb"))),
            ("workflow_attachment", ("data/genome.fa", open(RESOURCE_BASE_PATH.joinpath("data/genome.fa"), "rb"))),
            ("workflow_attachment", ("data/genome.fa.amb", open(RESOURCE_BASE_PATH.joinpath("data/genome.fa.amb"), "rb"))),
            ("workflow_attachment", ("data/genome.fa.fai", open(RESOURCE_BASE_PATH.joinpath("data/genome.fa.fai"), "rb"))),
            ("workflow_attachment", ("data/genome.fa.sa", open(RESOURCE_BASE_PATH.joinpath("data/genome.fa.sa"), "rb"))),
            ("workflow_attachment", ("data/genome.fa.pac", open(RESOURCE_BASE_PATH.joinpath("data/genome.fa.pac"), "rb"))),
            ("workflow_attachment", ("data/genome.fa.ann", open(RESOURCE_BASE_PATH.joinpath("data/genome.fa.ann"), "rb"))),
            ("workflow_attachment", ("data/genome.fa.bwt", open(RESOURCE_BASE_PATH.joinpath("data/genome.fa.bwt"), "rb"))),
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
    assert data["outputs"] != 0
