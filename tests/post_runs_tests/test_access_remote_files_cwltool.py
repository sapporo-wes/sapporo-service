#!/usr/bin/env python3
# coding: utf-8
import json
from argparse import Namespace
from pathlib import Path
from time import sleep
from typing import Dict, Union

from flask import Flask
from flask.testing import FlaskClient
from flask.wrappers import Response
from py._path.local import LocalPath

from sapporo.app import create_app, handle_default_params, parse_args
from sapporo.type import RunId, RunLog, RunRequest


def access_remote_files(client: FlaskClient) -> Response:  # type: ignore
    data: RunRequest = {
        "workflow_params": json.dumps({
            "fastq_1": {
                "class": "File",
                "location": "https://raw.githubusercontent.com/suecharo/" +
                            "genpei/master/tests/resources/" +
                            "ERR034597_1.small.fq.gz"
            },
            "fastq_2": {
                "class": "File",
                "location": "https://raw.githubusercontent.com/suecharo/" +
                            "genpei/master/tests/resources/" +
                            "ERR034597_2.small.fq.gz"
            }
        }),
        "workflow_type": "CWL",
        "workflow_type_version": "v1.0",
        "tags": json.dumps({
            "workflow_name": "trimming_and_qc_remote"  # type: ignore
        }),
        "workflow_engine_name": "cwltool",
        "workflow_engine_parameters": json.dumps({}),
        "workflow_url": "https://raw.githubusercontent.com/suecharo/" +
                        "genpei/master/tests/resources/" +
                        "trimming_and_qc_remote.cwl"
    }
    response: Response = client.post("/runs", data=data,
                                     content_type="multipart/form-data")

    return response


def test_access_remote_files(delete_env_vars: None,
                             tmpdir: LocalPath) -> None:
    args: Namespace = parse_args(["--run-dir", str(tmpdir)])
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)
    app.debug = params["debug"]  # type: ignore
    app.testing = True
    client: FlaskClient[Response] = app.test_client()
    posts_res: Response = access_remote_files(client)
    posts_res_data: RunId = posts_res.get_json()

    assert posts_res.status_code == 200
    assert "run_id" in posts_res_data

    run_id: str = posts_res_data["run_id"]
    sleep(3)
    from ..test_get_run_id import get_run_id
    res: Response = get_run_id(client, run_id)
    res_data: RunLog = res.get_json()

    assert res.status_code == 200
    assert "run_id" in res_data
    assert run_id == res_data["run_id"]
