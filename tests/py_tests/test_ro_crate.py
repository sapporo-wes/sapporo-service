# pylint: disable=C0415, W0613, W0621

import json
from time import sleep

from .conftest import anyhow_get_test_client, post_run, wait_for_run
from .test_run_cwltool import remote_wf_run_request


def test_generate_ro_crate(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **remote_wf_run_request)  # type: ignore
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    state = wait_for_run(client, run_id)
    assert state == "COMPLETE"

    from sapporo.config import RUN_DIR_STRUCTURE
    ro_crate_path = tmpdir.joinpath(f"{run_id[:2]}/{run_id}/{RUN_DIR_STRUCTURE['ro_crate']}")
    count = 0
    while count <= 20:
        sleep(3)
        if ro_crate_path.exists():
            break
    assert ro_crate_path.exists()

    with ro_crate_path.open(mode="r", encoding="utf-8") as f:
        ro_crate = json.load(f)
    assert ro_crate.keys() != 0
