# pylint: disable=C0415, W0613, W0621

from .conftest import anyhow_get_test_client
from .test_post_cwltool import post_run_cwltool_remote_wf


def test_get_run_id_status(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    run_id = post_run_cwltool_remote_wf(client)  # type: ignore

    response = client.get(f"/runs/{run_id}/status")
    assert response.status_code == 200
    data = response.json()

    assert data["run_id"] == run_id
    assert data["state"] == "COMPLETE"


def test_get_run_id_status_invalid_run_id(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = client.get("/runs/invalid_run_id/status")
    assert response.status_code == 404
