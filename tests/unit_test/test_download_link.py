#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=unused-argument
from pathlib import Path
from uuid import uuid4

from py._path.local import LocalPath

from sapporo.app import create_app
from sapporo.config import get_config, parse_args


def test_download_link(delete_env_vars: None, tmpdir: LocalPath) -> None:
    args = parse_args(["--run-dir", str(tmpdir)])
    config = get_config(args)
    app = create_app(config)
    app.debug = config["debug"]
    app.testing = True
    client = app.test_client()

    run_id = str(uuid4())
    run_dir = Path(tmpdir).joinpath(f"{run_id[:2]}/{run_id}")
    run_dir.mkdir(parents=True, exist_ok=True)
    with run_dir.joinpath("run_request.json").open(mode="w", encoding="utf-8") as f:
        f.write("")
    with run_dir.joinpath("test.txt").open(mode="w", encoding="utf-8") as f:
        f.write("test")
    run_dir.joinpath("test").mkdir(parents=True, exist_ok=True)
    with run_dir.joinpath("test/test.txt").open(mode="w", encoding="utf-8") as f:
        f.write("test")

    res_file = client.get(f"/runs/{run_id}/data/test.txt")
    assert res_file.data.decode("utf-8") == "test"

    res_dir = client.get(f"/runs/{run_id}/data/test")
    res_data = res_dir.get_json()
    assert res_data["name"] == "test"  # type: ignore
    assert res_data["path"] == "."  # type: ignore
    assert res_data["type"] == "directory"  # type: ignore
    assert "children" in res_data  # type: ignore
    assert res_data["children"][0]["name"] == "test.txt"  # type: ignore
    assert res_data["children"][0]["path"] == "test.txt"  # type: ignore
    assert res_data["children"][0]["type"] == "file"  # type: ignore

    res = client.get(f"/runs/{run_id}/data/test?download=true")
    assert res.status_code == 200
