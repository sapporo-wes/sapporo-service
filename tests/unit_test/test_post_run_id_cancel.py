# coding: utf-8
# pylint: disable=unused-argument
from time import sleep

from flask.testing import FlaskClient

from .conftest import run_workflow


def test_get_run_id_cancel(delete_env_vars: None, test_client: FlaskClient) -> None:  # type: ignore
    run_id = run_workflow(test_client)

    sleep(3)
    res = test_client.post(f"/runs/{run_id}/cancel")
    res_data = res.get_json()

    count = 0
    while count <= 120:
        sleep(3)
        res = test_client.get(f"/runs/{run_id}")
        res_data = res.get_json()
        if res_data["state"] in ["COMPLETE", "EXECUTOR_ERROR", "SYSTEM_ERROR", "CANCELED"]:
            break
        count += 1
    if count > 120:
        raise TimeoutError(f"Run {run_id} did not complete in time.")
    assert res_data["state"] == "CANCELED"
