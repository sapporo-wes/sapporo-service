# pylint: disable=C0415, W0613, W0621

from time import sleep

from .conftest import anyhow_get_test_client, post_run, wait_for_run
from .test_run_cwltool import remote_wf_run_request


def test_cancel_run(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **remote_wf_run_request)  # type: ignore
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    sleep(3)

    response = client.post(f"/runs/{run_id}/cancel")
    assert response.status_code == 200

    state = wait_for_run(client, run_id)
    assert state == "CANCELED"
