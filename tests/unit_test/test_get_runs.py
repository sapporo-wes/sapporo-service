#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=import-outside-toplevel, unused-argument
from time import sleep
from typing import Any, cast

from flask.testing import FlaskClient
from py._path.local import LocalPath

from sapporo.app import create_app
from sapporo.config import get_config, parse_args
from sapporo.model import RunListResponse


def get_runs(client: FlaskClient) -> Any:  # type: ignore
    res = client.get("/runs")

    return res


def test_get_runs(delete_env_vars: None, tmpdir: LocalPath) -> None:
    args = parse_args(["--run-dir", str(tmpdir)])
    config = get_config(args)
    app = create_app(config)
    app.debug = config["debug"]
    app.testing = True
    client = app.test_client()

    from .test_post_runs.cwltool.test_remote_workflow import \
        post_runs_remote_workflow_with_flask
    posts_res_data = post_runs_remote_workflow_with_flask(client)
    run_id: str = posts_res_data["run_id"]
    sleep(3)

    res = get_runs(client)
    res_data = cast(RunListResponse, res.get_json())

    assert res.status_code == 200
    assert "runs" in res_data
    assert len(res_data["runs"]) == 1
    assert "run_id" in res_data["runs"][0]
    assert "state" in res_data["runs"][0]
    assert run_id == res_data["runs"][0]["run_id"]
