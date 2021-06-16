#!/usr/bin/env python3
# coding: utf-8
from time import sleep

from py._path.local import LocalPath
from werkzeug.test import TestResponse

from sapporo.app import create_app, handle_default_params, parse_args
from sapporo.type import RunLog, RunStatus


def test_disable_workflow_attachment(delete_env_vars: None,
                                     tmpdir: LocalPath) -> None:
    args = parse_args(["--disable-workflow-attachment",
                       "--run-dir", str(tmpdir)])
    params = handle_default_params(args)
    app = create_app(params)
    app.debug = params["debug"]  # type: ignore
    app.testing = True
    client = app.test_client()

    from .test_post_runs.cwltool.test_attach_all_files import \
        post_runs_attach_all_files_with_flask
    post_runs_data = post_runs_attach_all_files_with_flask(client)
    run_id = post_runs_data["run_id"]

    from .test_get_run_id_status import get_run_id_status
    count = 0
    while count <= 120:
        sleep(3)
        get_status_res = get_run_id_status(client, run_id)
        get_status_data: RunStatus = get_status_res.get_json()  # type: ignore
        if get_status_data["state"] == "EXECUTOR_ERROR":  # type: ignore
            break
        count += 1
    assert str(get_status_data["state"]) == "EXECUTOR_ERROR"

    from .test_get_run_id import get_run_id
    detail_res: TestResponse = get_run_id(client, run_id)
    detail_res_data: RunLog = detail_res.get_json()  # type: ignore

    assert detail_res.status_code == 200
    assert detail_res_data["run_log"]["exit_code"] == 1
    assert "Not found" in detail_res_data["run_log"]["stderr"]
