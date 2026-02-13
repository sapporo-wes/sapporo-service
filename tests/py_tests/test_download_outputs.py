import io
import zipfile

from .conftest import anyhow_get_test_client, post_run, wait_for_run
from .test_run_cwltool import remote_wf_run_request


def test_get_run_outputs_list(mocker, tmpdir):  # type: ignore[no-untyped-def]
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **remote_wf_run_request)  # type: ignore[arg-type]
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    state = wait_for_run(client, run_id)
    if state != "COMPLETE":
        response = client.get(f"/runs/{run_id}")
        print(response.json())
    assert state == "COMPLETE"

    response = client.get(f"/runs/{run_id}/outputs")
    assert response.status_code == 200


def test_download_zip_outputs(mocker, tmpdir):  # type: ignore[no-untyped-def]
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **remote_wf_run_request)  # type: ignore[arg-type]
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    state = wait_for_run(client, run_id)
    if state != "COMPLETE":
        response = client.get(f"/runs/{run_id}")
        print(response.json())
    assert state == "COMPLETE"

    response = client.get(f"/runs/{run_id}/outputs?download=true")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/zip"

    extract_dir = tmpdir.joinpath("extract")
    extract_dir.mkdir(parents=True, exist_ok=True)
    zip_file = io.BytesIO(response.content)
    with zipfile.ZipFile(zip_file) as zf:
        zf.extractall(extract_dir)

    outputs_dir_name = f"sapporo_{run_id}_outputs"
    expected_files = [
        extract_dir.joinpath(outputs_dir_name, "ERR034597_1.small_fastqc.html"),
        extract_dir.joinpath(outputs_dir_name, "ERR034597_1.small.fq.trimmed.1P.fq"),
        extract_dir.joinpath(outputs_dir_name, "ERR034597_1.small.fq.trimmed.1U.fq"),
        extract_dir.joinpath(outputs_dir_name, "ERR034597_1.small.fq.trimmed.2P.fq"),
        extract_dir.joinpath(outputs_dir_name, "ERR034597_1.small.fq.trimmed.2U.fq"),
        extract_dir.joinpath(outputs_dir_name, "ERR034597_2.small_fastqc.html"),
    ]

    for file in extract_dir.glob("**/*"):
        if file.is_dir():
            continue
        assert file in expected_files


def test_download_each_output(mocker, tmpdir):  # type: ignore[no-untyped-def]
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = post_run(client, **remote_wf_run_request)  # type: ignore[arg-type]
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]

    state = wait_for_run(client, run_id)
    if state != "COMPLETE":
        response = client.get(f"/runs/{run_id}")
        print(response.json())
    assert state == "COMPLETE"

    response = client.get(f"/runs/{run_id}/outputs/ERR034597_1.small_fastqc.html")
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]

    response = client.get(f"/runs/{run_id}/outputs/ERR034597_1.small.fq.trimmed.1P.fq")
    assert response.status_code == 200
    assert "text/plain" in response.headers["Content-Type"]
