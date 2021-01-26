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


def test_url_prefix(delete_env_vars: None, tmpdir: LocalPath) -> None:
    args: Namespace = parse_args(["--url-prefix", "/test"])
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)
    app.debug = params["debug"]
    app.testing = True
    client: FlaskClient[Response] = app.test_client()
    res: Response = client.get("/test/service-info")

    assert res.status_code == 200
