# coding: utf-8
# pylint: disable=unused-argument
from pathlib import Path
from uuid import uuid4

from .conftest import get_default_config, setup_test_client


def test_download_link(delete_env_vars: None, tmpdir: Path) -> None:
    config = get_default_config(tmpdir)
    config.update({"run_dir": tmpdir, })
    client = setup_test_client(config)
    res = client.get("/service-info")
    res_data = res.get_json()

    # Prepare files
    run_id = str(uuid4())
    run_dir = Path(tmpdir).joinpath(f"{run_id[:2]}/{run_id}")
    run_dir.mkdir(parents=True, exist_ok=True)
    with run_dir.joinpath("run_request.json").open(mode="w", encoding="utf-8") as f:
        f.write("test")
    with run_dir.joinpath("test.txt").open(mode="w", encoding="utf-8") as f:
        f.write("test")
    run_dir.joinpath("test").mkdir(parents=True, exist_ok=True)
    with run_dir.joinpath("test/test.txt").open(mode="w", encoding="utf-8") as f:
        f.write("test")

    res_file = client.get(f"/runs/{run_id}/data/test.txt")
    assert res_file.data.decode("utf-8") == "test"

    res_dir = client.get(f"/runs/{run_id}/data/test")
    res_data = res_dir.get_json()
    assert res_data["name"] == "test"
    assert res_data["path"] == "."
    assert res_data["type"] == "directory"
    assert "children" in res_data
    assert res_data["children"][0]["name"] == "test.txt"
    assert res_data["children"][0]["path"] == "test.txt"
    assert res_data["children"][0]["type"] == "file"

    res = client.get(f"/runs/{run_id}/data/test?download=true")
    assert res.status_code == 200
