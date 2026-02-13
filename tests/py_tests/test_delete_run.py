from time import sleep

from .conftest import anyhow_get_test_client, post_run, wait_for_run
from .test_run_cwltool import remote_wf_run_request


def test_delete_run(mocker, tmpdir):  # type: ignore[no-untyped-def]
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **remote_wf_run_request)  # type: ignore[arg-type]
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    sleep(3)

    response = client.delete(f"/runs/{run_id}")
    assert response.status_code == 200

    state = wait_for_run(client, run_id)
    assert state == "DELETED"
