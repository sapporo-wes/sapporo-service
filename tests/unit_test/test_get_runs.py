# coding: utf-8
# pylint: disable=unused-argument
from flask.testing import FlaskClient

from .conftest import run_workflow, wait_for_run_to_complete


def test_get_runs(delete_env_vars: None, test_client: FlaskClient) -> None:  # type: ignore
    run_id = run_workflow(test_client)
    wait_for_run_to_complete(test_client, run_id)

    res = test_client.get("/runs")
    res_data = res.get_json()

    assert res.status_code == 200
    assert "runs" in res_data
    assert len(res_data["runs"]) == 1
    assert "run_id" in res_data["runs"][0]
    assert "state" in res_data["runs"][0]
    assert run_id == res_data["runs"][0]["run_id"]
