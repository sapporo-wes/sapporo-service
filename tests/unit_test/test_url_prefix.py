#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=unused-argument
from sapporo.app import create_app
from sapporo.config import get_config, parse_args


def test_url_prefix(delete_env_vars: None) -> None:
    args = parse_args(["--url-prefix", "/test"])
    config = get_config(args)
    app = create_app(config)
    app.debug = config["debug"]
    app.testing = True
    client = app.test_client()
    res = client.get("/test/service-info")

    assert res.status_code == 200
