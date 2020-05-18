#!/usr/bin/env python3
# coding: utf-8
from argparse import Namespace
from pathlib import Path
from typing import Dict, Union

from _pytest.monkeypatch import MonkeyPatch
from flask import Flask

from sapporo.app import create_app, handle_default_params, parse_args
from sapporo.const import DEFAULT_HOST, DEFAULT_PORT

base_dir: Path = Path(__file__).parent.parent.resolve()


def test_default_params(delete_env_vars: None) -> None:
    args: Namespace = parse_args([])
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)

    assert params["host"] == DEFAULT_HOST
    assert params["port"] == DEFAULT_PORT
    assert params["debug"] is False
    assert app.config["GET_RUNS"] is True
    assert app.config["WORKFLOW_ATTACHMENT"] is True
    assert app.config["REGISTERED_ONLY_MODE"] is False
    assert app.config["SERVICE_INFO"] == \
        base_dir.joinpath("sapporo/service-info.json")
    assert app.config["AVAILABLE_WORKFLOWS_CONFIG"] == \
        base_dir.joinpath("sapporo/available_workflows_config.json")
    assert app.config["RUN_SH"] == \
        base_dir.joinpath("sapporo/run.sh")


def test_env_vars(delete_env_vars: None, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SAPPORO_HOST", "127.0.0.1")
    monkeypatch.setenv("SAPPORO_PORT", "8888")
    monkeypatch.setenv("SAPPORO_DEBUG", "True")
    monkeypatch.setenv("SAPPORO_RUN_DIR", str(base_dir.joinpath("tests/run")))
    monkeypatch.setenv("SAPPORO_GET_RUNS", "False")
    monkeypatch.setenv("SAPPORO_WORKFLOW_ATTACHMENT", "False")
    monkeypatch.setenv("SAPPORO_RUN_ONLY_REGISTERED_WORKFLOWS",
                       "True")
    monkeypatch.setenv("SAPPORO_SERVICE_INFO",
                       str(base_dir.joinpath("tests/service-info.json")))
    monkeypatch.setenv("SAPPORO_AVAILABLE_WORKFLOWS_CONFIG",
                       str(base_dir.joinpath("tests/available_workflows_config.json")))  # noqa: E501
    monkeypatch.setenv("SAPPORO_RUN_SH",
                       str(base_dir.joinpath("tests/run.sh")))

    args: Namespace = parse_args([])
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)

    assert params["host"] == "127.0.0.1"
    assert params["port"] == 8888
    assert params["debug"] is True
    assert app.config["RUN_DIR"] == base_dir.joinpath("tests/run")
    assert app.config["GET_RUNS"] is False
    assert app.config["WORKFLOW_ATTACHMENT"] is False
    assert app.config["REGISTERED_ONLY_MODE"] is True
    assert app.config["SERVICE_INFO"] == \
        base_dir.joinpath("tests/service-info.json")
    assert app.config["AVAILABLE_WORKFLOWS_CONFIG"] == \
        base_dir.joinpath("tests/available_workflows_config.json")
    assert app.config["RUN_SH"] == \
        base_dir.joinpath("tests/run.sh")


def test_parse_args(delete_env_vars: None) -> None:
    args: Namespace = \
        parse_args(["--host", "127.0.0.1",
                    "--port", "8888",
                    "--debug",
                    "--run-dir", str(base_dir.joinpath("tests/run")),
                    "--disable-get-runs",
                    "--disable-workflow-attachment",
                    "--run-only-registered-workflows",
                    "--service-info",
                    str(base_dir.joinpath("tests/service-info.json")),
                    "--available-workflows-config",
                    str(base_dir.joinpath("tests/available_workflows_config.json")),  # noqa: E501
                    "--run-sh",
                    str(base_dir.joinpath("tests/run.sh"))])
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)

    assert params["host"] == "127.0.0.1"
    assert params["port"] == 8888
    assert params["debug"] is True
    assert app.config["RUN_DIR"] == base_dir.joinpath("tests/run")
    assert app.config["GET_RUNS"] is False
    assert app.config["WORKFLOW_ATTACHMENT"] is False
    assert app.config["REGISTERED_ONLY_MODE"] is True
    assert app.config["SERVICE_INFO"] == \
        base_dir.joinpath("tests/service-info.json")
    assert app.config["AVAILABLE_WORKFLOWS_CONFIG"] == \
        base_dir.joinpath("tests/available_workflows_config.json")
    assert app.config["RUN_SH"] == \
        base_dir.joinpath("tests/run.sh")
