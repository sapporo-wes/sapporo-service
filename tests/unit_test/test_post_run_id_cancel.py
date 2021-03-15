#!/usr/bin/env python3
# coding: utf-8
from time import sleep

from flask.testing import FlaskClient
from flask.wrappers import Response
from py._path.local import LocalPath

from sapporo.app import create_app, handle_default_params, parse_args
from sapporo.type import RunId, RunLog, RunStatus


def post_run_id_cancel(client: FlaskClient,  # type: ignore
                       run_id: str) -> Response:
    res: Response = client.post(f"/runs/{run_id}/cancel")

    return res


def test_post_run_id_cancel(delete_env_vars: None, tmpdir: LocalPath) -> None:
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

    posts_cancel_res: Response = post_run_id_cancel(client, run_id)
    posts_cancel_res_data: RunId = posts_cancel_res.get_json()

    assert posts_cancel_res.status_code == 200
    assert "run_id" in posts_cancel_res_data
    assert run_id == posts_cancel_res_data["run_id"]

    from .test_get_run_id_status import get_run_id_status
    count: int = 0
    while count <= 120:
        sleep(3)
        get_status_res: Response = get_run_id_status(client, run_id)
        get_status_data: RunStatus = get_status_res.get_json()
        if str(get_status_data["state"]) in \
                ["COMPLETE", "EXECUTOR_ERROR", "SYSTEM_ERROR", "CANCELED"]:
            break
        count += 1
    assert str(get_status_data["state"]) == "CANCELED"

    from .test_get_run_id import get_run_id
    detail_res: Response = get_run_id(client, run_id)
    detail_res_data: RunLog = detail_res.get_json()

    assert detail_res.status_code == 200
    assert detail_res_data["run_log"]["exit_code"] == 138
