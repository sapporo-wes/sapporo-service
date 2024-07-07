# pylint: disable=C0415, W0613, W0621

from .conftest import anyhow_get_test_client
from .test_run_cwltool import run_cwltool_remote_wf


def test_get_run_id(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    run_id = run_cwltool_remote_wf(client)  # type: ignore

    response = client.get(f"/runs/{run_id}")
    assert response.status_code == 200


def test_get_run_id_invalid_run_id(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = client.get("/runs/invalid_run_id")
    assert response.status_code == 404
