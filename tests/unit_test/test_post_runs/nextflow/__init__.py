#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path
from typing import Dict

from ...conftest import TEST_HOST, TEST_PORT

TEST_HOST = TEST_HOST
TEST_PORT = TEST_PORT

SCRIPT_DIR = Path(__file__).parent.parent.parent.parent.joinpath(
    "curl_example/post_runs/nextflow").resolve()
RESOURCE_DIR: Path = Path(__file__).parent.parent.parent.parent.joinpath(
    "resources/nextflow").resolve()
REMOTE_URL: str = "https://raw.githubusercontent.com/ddbj/" +\
    "sapporo-service/master/tests/resources/nextflow/"

RESOURCE: Dict[str, Path] = {
    "FILE_INPUT": RESOURCE_DIR.joinpath("file_input.nf"),
    "NF_TEST_INPUT": RESOURCE_DIR.joinpath("nf_test_input.txt"),
    "PARAMS_OUTDIR": RESOURCE_DIR.joinpath("params_outdir.nf"),
    "STR_INPUT": RESOURCE_DIR.joinpath("str_input.nf")
}
RESOURCE_REMOTE: Dict[str, str] = {
    "FILE_INPUT": REMOTE_URL + "file_input.nf",
    "NF_TEST_INPUT": REMOTE_URL + "nf_test_input.txt",
    "PARAMS_OUTDIR": REMOTE_URL + "params_outdir.nf",
    "STR_INPUT": REMOTE_URL + "str_input.nf"
}
