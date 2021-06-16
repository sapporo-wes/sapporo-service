#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path
from uuid import uuid4

from py._path.local import LocalPath
from werkzeug.test import TestResponse

from sapporo.app import create_app, handle_default_params, parse_args


def test_download_link(delete_env_vars: None, tmpdir: LocalPath) -> None:
    args = parse_args(["--run-dir", str(tmpdir)])
    params = handle_default_params(args)
    app = create_app(params)
    app.debug = params["debug"]  # type: ignore
    app.testing = True
    client = app.test_client()

    run_id = str(uuid4())
    run_dir = Path(tmpdir).joinpath(f"{run_id[:2]}/{run_id}")
    run_dir.mkdir(parents=True, exist_ok=True)
    with run_dir.joinpath("run_request.json").open(mode="w") as f:
        f.write("")
    with run_dir.joinpath("test.txt").open(mode="w") as f:
        f.write("test")
    run_dir.joinpath("test").mkdir(parents=True, exist_ok=True)
    with run_dir.joinpath("test/test.txt").open(mode="w") as f:
        f.write("test")

    res_file: TestResponse = client.get(f"/runs/{run_id}/data/test.txt")
    assert res_file.data.decode("utf-8") == "test"

    res_dir: TestResponse = client.get(f"/runs/{run_id}/data/test")
    res_data = res_dir.get_json()
    assert "test" == res_data["name"]  # type: ignore
    assert "." == res_data["path"]  # type: ignore
    assert "directory" == res_data["type"]  # type: ignore
    assert "children" in res_data  # type: ignore
    assert "test.txt" == res_data["children"][0]["name"]  # type: ignore
    assert "test.txt" == res_data["children"][0]["path"]  # type: ignore
    assert "file" == res_data["children"][0]["type"]  # type: ignore

    res = client.get(f"/runs/{run_id}/data/test?download=true")
    assert res.status_code == 200
