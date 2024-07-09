# pylint: disable=C0415, W0613, W0621

import io
import json
import zipfile
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
    if state != "COMPLETE":
        response = client.get(f"/runs/{run_id}")
        print(response.json())
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


def test_get_ro_crate(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **remote_wf_run_request)  # type: ignore
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    state = wait_for_run(client, run_id)
    if state != "COMPLETE":
        response = client.get(f"/runs/{run_id}")
        print(response.json())
    assert state == "COMPLETE"

    from sapporo.config import RUN_DIR_STRUCTURE
    ro_crate_path = tmpdir.joinpath(f"{run_id[:2]}/{run_id}/{RUN_DIR_STRUCTURE['ro_crate']}")
    count = 0
    while count <= 20:
        sleep(3)
        if ro_crate_path.exists():
            break
    assert ro_crate_path.exists()

    response = client.get(f"/runs/{run_id}/ro-crate")
    assert response.status_code == 200


def test_download_zip_ro_crate(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **remote_wf_run_request)  # type: ignore
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    state = wait_for_run(client, run_id)
    if state != "COMPLETE":
        response = client.get(f"/runs/{run_id}")
        print(response.json())
    assert state == "COMPLETE"

    from sapporo.config import RUN_DIR_STRUCTURE
    ro_crate_path = tmpdir.joinpath(f"{run_id[:2]}/{run_id}/{RUN_DIR_STRUCTURE['ro_crate']}")
    count = 0
    while count <= 20:
        sleep(3)
        if ro_crate_path.exists():
            break
    assert ro_crate_path.exists()

    response = client.get(f"/runs/{run_id}/ro-crate?download=true")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/zip"

    extract_dir = tmpdir.joinpath("extract")
    extract_dir.mkdir(parents=True, exist_ok=True)
    zip_file = io.BytesIO(response.content)
    with zipfile.ZipFile(zip_file) as zf:
        zf.extractall(extract_dir)

    outputs_dir_name = f"sapporo_{run_id}_ro_crate"
    run_request_file = extract_dir.joinpath(outputs_dir_name, RUN_DIR_STRUCTURE["run_request"])

    assert run_request_file in extract_dir.glob("**/*")
