#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=unused-argument
from typing import cast

from cwl_inputs_parser.utils import download_file

from sapporo.app import create_app
from sapporo.config import get_config, parse_args
from sapporo.model import ParseResult

CWL_LOC = "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimming_and_qc_remote.cwl"
WDL_LOC = "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cromwell/dockstore-tool-bamstats/Dockstore.wdl"
NFL_LOC = "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/nextflow/file_input.nf"
SMK_LOC = "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/snakemake/Snakefile"


def test_parse_cwl_type_version(delete_env_vars: None) -> None:
    app = create_app(get_config(parse_args([])))
    app.testing = True
    client = app.test_client()
    res = client.post("/parse-workflow",
                      data={
                          "workflow_location": CWL_LOC
                      },
                      content_type="multipart/form-data")
    res_data = cast(ParseResult, res.get_json())
    assert res_data["inputs"] is None
    assert res_data["workflow_type"] == "CWL"
    assert res_data["workflow_type_version"] == "v1.0"


def test_parse_cwl_type_version_by_content(delete_env_vars: None) -> None:
    app = create_app(get_config(parse_args([])))
    app.testing = True
    client = app.test_client()
    res = client.post("/parse-workflow",
                      data={
                          "workflow_content": download_file(CWL_LOC)
                      },
                      content_type="multipart/form-data")
    res_data = cast(ParseResult, res.get_json())
    assert res_data["inputs"] is None
    assert res_data["workflow_type"] == "CWL"
    assert res_data["workflow_type_version"] == "v1.0"


def test_parse_cwl_inputs(delete_env_vars: None) -> None:
    app = create_app(get_config(parse_args([])))
    app.testing = True
    client = app.test_client()
    res = client.post("/parse-workflow",
                      data={
                          "workflow_location": CWL_LOC,
                          "types_of_parsing": ["inputs"]
                      },
                      content_type="multipart/form-data")
    res_data = cast(ParseResult, res.get_json())
    assert res_data["inputs"] is not None
    assert isinstance(res_data["inputs"], list)
    assert res_data["workflow_type"] == "CWL"
    assert res_data["workflow_type_version"] == "v1.0"


def test_parse_cwl_make_template(delete_env_vars: None) -> None:
    app = create_app(get_config(parse_args([])))
    app.testing = True
    client = app.test_client()
    res = client.post("/parse-workflow",
                      data={
                          "workflow_location": CWL_LOC,
                          "types_of_parsing": ["make_template"]
                      },
                      content_type="multipart/form-data")
    res_data = cast(ParseResult, res.get_json())
    assert res_data["inputs"] is not None
    assert isinstance(res_data["inputs"], str)
    assert res_data["workflow_type"] == "CWL"
    assert res_data["workflow_type_version"] == "v1.0"


def test_parse_wdl_type_version(delete_env_vars: None) -> None:
    app = create_app(get_config(parse_args([])))
    app.testing = True
    client = app.test_client()
    res = client.post("/parse-workflow",
                      data={
                          "workflow_location": WDL_LOC
                      },
                      content_type="multipart/form-data")
    res_data = cast(ParseResult, res.get_json())
    assert res_data["inputs"] is None
    assert res_data["workflow_type"] == "WDL"
    assert res_data["workflow_type_version"] == "1.0"


def test_parse_nfl_type_version(delete_env_vars: None) -> None:
    app = create_app(get_config(parse_args([])))
    app.testing = True
    client = app.test_client()
    res = client.post("/parse-workflow",
                      data={
                          "workflow_location": NFL_LOC
                      },
                      content_type="multipart/form-data")
    res_data = cast(ParseResult, res.get_json())
    assert res_data["inputs"] is None
    assert res_data["workflow_type"] == "NFL"
    assert res_data["workflow_type_version"] == "1.0"


def test_parse_smk_type_version(delete_env_vars: None) -> None:
    app = create_app(get_config(parse_args([])))
    app.testing = True
    client = app.test_client()
    res = client.post("/parse-workflow",
                      data={
                          "workflow_location": SMK_LOC
                      },
                      content_type="multipart/form-data")
    res_data = cast(ParseResult, res.get_json())
    assert res_data["inputs"] is None
    assert res_data["workflow_type"] == "SMK"
    assert res_data["workflow_type_version"] == "1.0"
