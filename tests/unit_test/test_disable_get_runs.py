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
from sapporo.type import ErrorResponse


def test_disable_get_runs(delete_env_vars: None, tmpdir: LocalPath) -> None:
    args: Namespace = parse_args(["--disable-get-runs",
                                  "--run-dir", str(tmpdir)])
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)
    app.debug = params["debug"]  # type: ignore
    app.testing = True
    client: FlaskClient[Response] = app.test_client()
    from .test_get_runs import get_runs
    get_runs_res: Response = get_runs(client)
    get_runs_data: ErrorResponse = get_runs_res.get_json()

    assert get_runs_res.status_code == 403
    assert "status_code" in get_runs_data
    assert get_runs_data["status_code"] == 403
    assert "msg" in get_runs_data
