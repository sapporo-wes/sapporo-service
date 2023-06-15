#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=unused-argument, too-many-locals, import-outside-toplevel
from pathlib import Path
from time import sleep
from typing import Any, cast

from flask.testing import FlaskClient

from sapporo.app import create_app
from sapporo.config import get_config, parse_args
from sapporo.model import RunId, RunLog, RunStatus


def post_run_id_cancel(client: FlaskClient, run_id: str) -> Any:  # type: ignore
    res = client.post(f"/runs/{run_id}/cancel")

    return res


def test_post_run_id_cancel(delete_env_vars: None, tmpdir: Path) -> None:
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

    posts_cancel_res = post_run_id_cancel(client, run_id)
    posts_cancel_res_data = cast(RunId, posts_cancel_res.get_json())

    assert posts_cancel_res.status_code == 200
    assert "run_id" in posts_cancel_res_data
    assert run_id == posts_cancel_res_data["run_id"]

    from .test_get_run_id_status import get_run_id_status
    count: int = 0
    while count <= 120:
        sleep(3)
        get_status_res = get_run_id_status(client, run_id)
        get_status_data = cast(RunStatus, get_status_res.get_json())
        if str(get_status_data["state"]) in \
                ["COMPLETE", "EXECUTOR_ERROR", "SYSTEM_ERROR", "CANCELED"]:
            break
        count += 1
    assert str(get_status_data["state"]) == "CANCELED"

    from .test_get_run_id import get_run_id
    detail_res = get_run_id(client, run_id)
    detail_res_data = cast(RunLog, detail_res.get_json())

    assert detail_res.status_code == 200
    assert detail_res_data["run_log"]["exit_code"] == 138
