#!/usr/bin/env python3
# coding: utf-8
from argparse import Namespace
from pathlib import Path
from typing import Dict, Union

from flask import Flask
from flask.testing import FlaskClient
from flask.wrappers import Response

from sapporo.app import create_app, handle_default_params, parse_args
from sapporo.type import ServiceInfo


def test_original_wes_mode(delete_env_vars: None) -> None:
    args: Namespace = parse_args([])
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)
    app.debug = params["debug"]
    app.testing = True
    client: FlaskClient[Response] = app.test_client()
    res: Response = client.get("/service-info")
    res_data: ServiceInfo = res.get_json()

    assert res.status_code == 200
    assert "auth_instructions_url" in res_data
    assert "contact_info_url" in res_data
    assert "default_workflow_engine_parameters" in res_data
    assert "supported_wes_versions" in res_data
    assert res_data["supported_wes_versions"][0] == "1.0.0"
    assert "system_state_counts" in res_data
    assert "tags" in res_data
    assert bool(res_data["tags"]["debug"]) is False
    assert bool(res_data["tags"]["get_runs"]) is True
    assert bool(res_data["tags"]["registered_only_mode"]) is False
    assert "run_dir" in res_data["tags"]
    assert res_data["tags"]["wes_name"] == "sapporo"
    assert "workflow_engine_versions" in res_data
    assert "workflow_type_versions" in res_data


def test_registered_only_mode(delete_env_vars: None) -> None:
    args: Namespace = parse_args([
        "--debug",
        "--disable-get-runs",
        "--run-only-registered-workflows",
    ])
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)
    app.debug = params["debug"]
    app.testing = True
    client: FlaskClient[Response] = app.test_client()
    res: Response = client.get("/service-info")
    res_data: ServiceInfo = res.get_json()

    assert res.status_code == 200
    assert "auth_instructions_url" in res_data
    assert "contact_info_url" in res_data
    assert "default_workflow_engine_parameters" in res_data
    assert "supported_wes_versions" in res_data
    assert res_data["supported_wes_versions"][0] == "sapporo-wes-1.0.0"
    assert "system_state_counts" in res_data
    assert "tags" in res_data
    assert bool(res_data["tags"]["debug"]) is True
    assert bool(res_data["tags"]["get_runs"]) is False
    assert bool(res_data["tags"]["registered_only_mode"]) is True
    assert "run_dir" in res_data["tags"]
    assert res_data["tags"]["wes_name"] == "sapporo"
    assert "workflow_engine_versions" in res_data
    assert "workflow_type_versions" in res_data
    assert "executable_workflows" in res_data
