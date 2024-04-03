# coding: utf-8
# pylint: disable=unused-argument
from flask.testing import FlaskClient

from .conftest import run_workflow, wait_for_run_to_complete


def test_get_run_id(delete_env_vars: None, test_client: FlaskClient) -> None:  # type: ignore
    run_id = run_workflow(test_client)
    wait_for_run_to_complete(test_client, run_id)

    res = test_client.get(f"/runs/{run_id}")
    res_data = res.get_json()

    assert res.status_code == 200
    assert "run_id" in res_data
    assert run_id == res_data["run_id"]
    assert "request" in res_data
    assert "workflow_params" in res_data["request"]
    assert "workflow_type" in res_data["request"]
    assert "workflow_type_version" in res_data["request"]
    assert "tags" in res_data["request"]
    assert "workflow_engine" in res_data["request"]
    assert "workflow_engine_parameters" in res_data["request"]
    assert "workflow_url" in res_data["request"]
    assert "state" in res_data
    assert "run_log" in res_data
    assert "name" in res_data["run_log"]
    assert "cmd" in res_data["run_log"]
    assert "start_time" in res_data["run_log"]
    assert "end_time" in res_data["run_log"]
    assert "stdout" in res_data["run_log"]
    assert "stderr" in res_data["run_log"]
    assert "exit_code" in res_data["run_log"]
    assert "task_logs" in res_data
    assert "outputs" in res_data
