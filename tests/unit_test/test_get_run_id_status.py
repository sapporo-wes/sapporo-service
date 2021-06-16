#!/usr/bin/env python3
# coding: utf-8
from time import sleep

from flask.testing import FlaskClient
from py._path.local import LocalPath
from werkzeug.test import TestResponse

from sapporo.app import create_app, handle_default_params, parse_args
from sapporo.type import RunStatus


def get_run_id_status(client: FlaskClient,  # type: ignore
                      run_id: str) -> TestResponse:
    res: TestResponse = client.get(f"/runs/{run_id}/status")

    return res


def test_get_runs(delete_env_vars: None, tmpdir: LocalPath) -> None:
    args = parse_args(["--run-dir", str(tmpdir)])
    params = handle_default_params(args)
    app = create_app(params)
    app.debug = params["debug"]  # type: ignore
    app.testing = True
    client = app.test_client()

    from .test_post_runs.cwltool.test_remote_workflow import \
        post_runs_remote_workflow_with_flask
    posts_res_data = post_runs_remote_workflow_with_flask(client)
    run_id: str = posts_res_data["run_id"]
    sleep(3)

    res = get_run_id_status(client, run_id)
    res_data: RunStatus = res.get_json()  # type: ignore

    assert res.status_code == 200
    assert "run_id" in res_data
    assert "state" in res_data
    assert run_id == res_data["run_id"]
