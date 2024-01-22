# coding: utf-8
# pylint: disable=unused-argument
from pathlib import Path

from .conftest import get_default_config, setup_test_client


def test_disable_get_runs(delete_env_vars: None, tmpdir: Path) -> None:
    config = get_default_config(tmpdir)
    config.update({
        "get_runs": False,
    })
    client = setup_test_client(config)
    res = client.get("/runs")
    res_data = res.get_json()

    assert res.status_code == 403
    assert "status_code" in res_data
    assert res_data["status_code"] == 403
    assert "msg" in res_data
