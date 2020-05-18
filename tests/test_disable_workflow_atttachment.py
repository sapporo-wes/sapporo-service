#!/usr/bin/env python3
# coding: utf-8
from argparse import Namespace
from pathlib import Path
from typing import Dict, Union

from flask import Flask
from flask.testing import FlaskClient
from flask.wrappers import Response
from py._path.local import LocalPath

from sapporo.app import create_app, handle_default_params, parse_args
from sapporo.type import RunId, RunLog, RunStatus


def test_disable_get_runs(delete_env_vars: None, tmpdir: LocalPath) -> None:
    args: Namespace = parse_args(["--disable-workflow-attachment",
                                  "--run-dir", str(tmpdir)])
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)
    app.debug = params["debug"]  # type: ignore
    app.testing = True
    client: FlaskClient[Response] = app.test_client()

    from .post_runs_tests.test_attach_all_files_cwltool \
        import attach_all_files
    post_runs_res: Response = attach_all_files(client)
    post_runs_data: RunId = post_runs_res.get_json()

    assert post_runs_res.status_code == 200

    run_id: str = post_runs_data["run_id"]
    from .test_get_run_id_status import get_run_id_status
    count = 0
    while count <= 10:
        get_status_res: Response = get_run_id_status(client, run_id)
        get_status_data: RunStatus = get_status_res.get_json()
        if get_status_data["state"] == "EXECUTOR_ERROR":  # type: ignore
            break

    from .test_get_run_id import get_run_id
    detail_res: Response = get_run_id(client, run_id)
    detail_res_data: RunLog = detail_res.get_json()

    assert detail_res.status_code == 200
    assert detail_res_data["run_log"]["exit_code"] == "1"  # type: ignore
    assert "Not found" in detail_res_data["run_log"]["stderr"]
