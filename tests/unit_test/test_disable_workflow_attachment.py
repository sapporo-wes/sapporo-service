#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=unused-argument, import-outside-toplevel
from pathlib import Path

import pytest

from sapporo.app import create_app
from sapporo.config import get_config, parse_args


def test_disable_workflow_attachment(delete_env_vars: None, tmpdir: Path) -> None:
    args = parse_args(
        ["--disable-workflow-attachment", "--run-dir", str(tmpdir)])
    config = get_config(args)
    app = create_app(config)
    app.debug = config["debug"]
    app.testing = True
    client = app.test_client()

    from .test_post_runs.cwltool.test_attach_all_files import \
        post_runs_attach_all_files_with_flask
    with pytest.raises(AssertionError):
        post_runs_attach_all_files_with_flask(client)
