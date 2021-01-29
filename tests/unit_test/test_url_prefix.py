#!/usr/bin/env python3
# coding: utf-8
from sapporo.app import create_app, handle_default_params, parse_args


def test_url_prefix(delete_env_vars: None) -> None:
    args = parse_args(["--url-prefix", "/test"])
    params = handle_default_params(args)
    app = create_app(params)
    app.debug = params["debug"]  # type: ignore
    app.testing = True
    client = app.test_client()
    res = client.get("/test/service-info")

    assert res.status_code == 200
