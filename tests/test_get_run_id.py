#!/usr/bin/env python3
# coding: utf-8
from argparse import Namespace
from pathlib import Path
from time import sleep
from typing import Dict, Union

from flask import Flask
from flask.testing import FlaskClient
from flask.wrappers import Response
from py._path.local import LocalPath

from sapporo.app import create_app, handle_default_params, parse_args
from sapporo.type import RunId, RunLog


def get_run_id(client: FlaskClient,  # type: ignore
               run_id: str) -> Response:
    response: Response = client.get(f"/runs/{run_id}")

    return response


def test_get_run_id(delete_env_vars: None, tmpdir: LocalPath) -> None:
    args: Namespace = parse_args(["--run-dir", str(tmpdir)])
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)
    app.debug = params["debug"]  # type: ignore
    app.testing = True
    client: FlaskClient[Response] = app.test_client()
    from .post_runs_tests.test_access_remote_files_cwltool import \
        access_remote_files
    posts_res: Response = access_remote_files(client)
    posts_res_data: RunId = posts_res.get_json()

    assert posts_res.status_code == 200

    run_id: str = posts_res_data["run_id"]
    sleep(3)
    res: Response = get_run_id(client, run_id)
    res_data: RunLog = res.get_json()

    assert res.status_code == 200
    assert "run_id" in res_data
    assert run_id == res_data["run_id"]
    assert "request" in res_data
    assert "workflow_params" in res_data["request"]
    assert "workflow_type" in res_data["request"]
    assert "workflow_type_version" in res_data["request"]
    assert "tags" in res_data["request"]
    assert "workflow_engine_name" in res_data["request"]
    assert "workflow_engine_parameters" in res_data["request"]
    assert "workflow_url" in res_data["request"]
    assert "state" in res_data
    assert "run_log" in res_data
    assert "name" in res_data["run_log"]
    assert "cmd" in res_data["run_log"]
    assert "start_time" in res_data["run_log"]
    assert "end_time" in res_data["run_log"]
    assert "stdout" in res_data["run_log"]
    assert "stderr" in res_data["run_log"]
    assert "exit_code" in res_data["run_log"]
    assert "task_logs" in res_data
    assert "outputs" in res_data
