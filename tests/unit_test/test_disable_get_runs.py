#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=unused-argument, import-outside-toplevel
from typing import cast

from py._path.local import LocalPath

from sapporo.app import create_app
from sapporo.config import get_config, parse_args
from sapporo.model import ErrorResponse


def test_disable_get_runs(delete_env_vars: None, tmpdir: LocalPath) -> None:
    args = parse_args(["--disable-get-runs", "--run-dir", str(tmpdir)])
    config = get_config(args)
    app = create_app(config)
    app.debug = config["debug"]
    app.testing = True
    client = app.test_client()
    from .test_get_runs import get_runs
    get_runs_res = get_runs(client)
    get_runs_data = cast(ErrorResponse, get_runs_res.get_json())

    assert get_runs_res.status_code == 403
    assert "status_code" in get_runs_data
    assert get_runs_data["status_code"] == 403
    assert "msg" in get_runs_data
