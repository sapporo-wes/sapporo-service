#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=unused-argument, import-outside-toplevel
from pathlib import Path
from time import sleep
from typing import Any

from flask.testing import FlaskClient

from sapporo.app import create_app
from sapporo.config import get_config, parse_args
from sapporo.model import RunStatus


def get_run_id_status(client: FlaskClient, run_id: str) -> Any:  # type: ignore
    res = client.get(f"/runs/{run_id}/status")

    return res


def test_get_runs(delete_env_vars: None, tmpdir: Path) -> None:
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

    res = get_run_id_status(client, run_id)
    res_data: RunStatus = res.get_json()

    assert res.status_code == 200
    assert "run_id" in res_data
    assert "state" in res_data
    assert run_id == res_data["run_id"]
