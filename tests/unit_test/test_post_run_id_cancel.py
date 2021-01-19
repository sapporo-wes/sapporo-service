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
from sapporo.type import RunId, RunLog, RunStatus


def post_run_id_cancel(client: FlaskClient,  # type: ignore
                       run_id: str) -> Response:
    response: Response = client.post(f"/runs/{run_id}/cancel")

    return response


def test_post_run_id_cancel(delete_env_vars: None, tmpdir: LocalPath) -> None:
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
    posts_cancel_res: Response = post_run_id_cancel(client, run_id)
    posts_cancel_res_data: RunId = posts_cancel_res.get_json()

    assert posts_cancel_res.status_code == 200
    assert "run_id" in posts_cancel_res_data
    assert run_id == posts_cancel_res_data["run_id"]

    from .test_get_run_id_status import get_run_id_status
    count: int = 0
    while count <= 60:
        get_status_res: Response = get_run_id_status(client, run_id)
        get_status_data: RunStatus = get_status_res.get_json()
        if get_status_data["state"] == "CANCELED":  # type: ignore
            break
        sleep(1)
        count += 1

    from .test_get_run_id import get_run_id
    detail_res: Response = get_run_id(client, run_id)
    detail_res_data: RunLog = detail_res.get_json()

    assert detail_res.status_code == 200
    assert detail_res_data["run_log"]["exit_code"] == 138
