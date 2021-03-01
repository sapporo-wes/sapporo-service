#!/usr/bin/env python3
# coding: utf-8
from sapporo.app import create_app, handle_default_params, parse_args
from sapporo.type import ServiceInfo


def test_original_wes_mode(delete_env_vars: None) -> None:
    args = parse_args([])
    params = handle_default_params(args)
    app = create_app(params)
    app.debug = params["debug"]  # type: ignore
    app.testing = True
    client = app.test_client()
    res = client.get("/service-info")
    res_data: ServiceInfo = res.get_json()

    assert res.status_code == 200
    assert "auth_instructions_url" in res_data
    assert "contact_info_url" in res_data
    assert "default_workflow_engine_parameters" in res_data
    assert "executable_workflows" in res_data
    assert "supported_filesystem_protocols" in res_data
    assert "supported_wes_versions" in res_data
    assert res_data["supported_wes_versions"][0] == "sapporo-wes-1.0.0"
    assert "system_state_counts" in res_data
    assert "tags" in res_data
    assert bool(res_data["tags"]["debug"]) is False
    assert bool(res_data["tags"]["get_runs"]) is True
    assert bool(res_data["tags"]["registered_only_mode"]) is False
    assert res_data["tags"]["wes_name"] == "sapporo"
    assert bool(res_data["tags"]["workflow_attachment"]) is True
    assert "workflow_engine_versions" in res_data
    assert "workflow_type_versions" in res_data


def test_arguments(delete_env_vars: None) -> None:
    args = parse_args([
        "--debug",
        "--disable-get-runs",
        "--disable-workflow-attachment",
        "--run-only-registered-workflows",
    ])
    params = handle_default_params(args)
    app = create_app(params)
    app.debug = params["debug"]  # type: ignore
    app.testing = True
    client = app.test_client()
    res = client.get("/service-info")
    res_data: ServiceInfo = res.get_json()

    assert res.status_code == 200
    assert "auth_instructions_url" in res_data
    assert "contact_info_url" in res_data
    assert "default_workflow_engine_parameters" in res_data
    assert "executable_workflows" in res_data
    assert "supported_filesystem_protocols" in res_data
    assert "supported_wes_versions" in res_data
    assert res_data["supported_wes_versions"][0] == "sapporo-wes-1.0.0"
    assert "system_state_counts" in res_data
    assert "tags" in res_data
    assert bool(res_data["tags"]["debug"]) is True
    assert bool(res_data["tags"]["get_runs"]) is False
    assert bool(res_data["tags"]["registered_only_mode"]) is True
    assert res_data["tags"]["wes_name"] == "sapporo"
    assert bool(res_data["tags"]["workflow_attachment"]) is False
    assert "workflow_engine_versions" in res_data
    assert "workflow_type_versions" in res_data
