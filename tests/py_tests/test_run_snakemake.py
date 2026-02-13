import json

from .conftest import anyhow_get_test_client, assert_run_complete, package_root, post_run, wait_for_run

RESOURCE_BASE_PATH = package_root().joinpath("tests/resources/snakemake")


def test_run_snakemake(mocker, tmpdir):  # type: ignore[no-untyped-def]
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(
        client,
        **{  # type: ignore[arg-type]
            "workflow_type": "SMK",
            "workflow_engine": "snakemake",
            "workflow_params": json.dumps({}),
            "workflow_url": "Snakefile",
            "workflow_engine_parameters": json.dumps(
                {
                    "--cores": "1",
                    "--use-conda": "",
                }
            ),
            "workflow_attachment": [
                ("workflow_attachment", ("Snakefile", RESOURCE_BASE_PATH.joinpath("Snakefile").open("rb"))),
                (
                    "workflow_attachment",
                    ("scripts/plot-quals.py", RESOURCE_BASE_PATH.joinpath("scripts/plot-quals.py").open("rb")),
                ),
                (
                    "workflow_attachment",
                    ("envs/stats.yaml", RESOURCE_BASE_PATH.joinpath("envs/stats.yaml").open("rb")),
                ),
                (
                    "workflow_attachment",
                    ("envs/calling.yaml", RESOURCE_BASE_PATH.joinpath("envs/calling.yaml").open("rb")),
                ),
                (
                    "workflow_attachment",
                    ("envs/mapping.yaml", RESOURCE_BASE_PATH.joinpath("envs/mapping.yaml").open("rb")),
                ),
                (
                    "workflow_attachment",
                    ("data/samples/A.fastq", RESOURCE_BASE_PATH.joinpath("data/samples/A.fastq").open("rb")),
                ),
                (
                    "workflow_attachment",
                    ("data/samples/B.fastq", RESOURCE_BASE_PATH.joinpath("data/samples/B.fastq").open("rb")),
                ),
                (
                    "workflow_attachment",
                    ("data/samples/C.fastq", RESOURCE_BASE_PATH.joinpath("data/samples/C.fastq").open("rb")),
                ),
                ("workflow_attachment", ("data/genome.fa", RESOURCE_BASE_PATH.joinpath("data/genome.fa").open("rb"))),
                (
                    "workflow_attachment",
                    ("data/genome.fa.amb", RESOURCE_BASE_PATH.joinpath("data/genome.fa.amb").open("rb")),
                ),
                (
                    "workflow_attachment",
                    ("data/genome.fa.fai", RESOURCE_BASE_PATH.joinpath("data/genome.fa.fai").open("rb")),
                ),
                (
                    "workflow_attachment",
                    ("data/genome.fa.sa", RESOURCE_BASE_PATH.joinpath("data/genome.fa.sa").open("rb")),
                ),
                (
                    "workflow_attachment",
                    ("data/genome.fa.pac", RESOURCE_BASE_PATH.joinpath("data/genome.fa.pac").open("rb")),
                ),
                (
                    "workflow_attachment",
                    ("data/genome.fa.ann", RESOURCE_BASE_PATH.joinpath("data/genome.fa.ann").open("rb")),
                ),
                (
                    "workflow_attachment",
                    ("data/genome.fa.bwt", RESOURCE_BASE_PATH.joinpath("data/genome.fa.bwt").open("rb")),
                ),
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    state = wait_for_run(client, run_id)
    if state != "COMPLETE":
        response = client.get(f"/runs/{run_id}")
        print(response.json())
    assert state == "COMPLETE"

    response = client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()

    assert_run_complete(run_id, data)
    assert data["outputs"] != 0
