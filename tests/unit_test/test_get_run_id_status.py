# coding: utf-8
# pylint: disable=unused-argument
from flask.testing import FlaskClient

from .conftest import run_workflow, wait_for_run_to_complete


def test_get_run_id_status(delete_env_vars: None, test_client: FlaskClient) -> None:  # type: ignore
    run_id = run_workflow(test_client)
    wait_for_run_to_complete(test_client, run_id)

    res = test_client.get(f"/runs/{run_id}/status")
    res_data = res.get_json()

    assert res.status_code == 200
    assert "run_id" in res_data
    assert "state" in res_data
    assert run_id == res_data["run_id"]
    assert res_data["state"] == "COMPLETE"
