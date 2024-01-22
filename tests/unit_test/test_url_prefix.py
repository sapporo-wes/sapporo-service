# coding: utf-8
# pylint: disable=unused-argument
from pathlib import Path

from .conftest import get_default_config, setup_test_client


def test_url_prefix(delete_env_vars: None, tmpdir: Path) -> None:
    config = get_default_config(tmpdir)
    config.update({
        "url_prefix": "/test",
    })
    client = setup_test_client(config)
    res = client.get("/test/service-info")

    assert res.status_code == 200
