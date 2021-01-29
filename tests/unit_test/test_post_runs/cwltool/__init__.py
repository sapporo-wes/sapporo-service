#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path
from typing import Dict

from ...conftest import TEST_HOST, TEST_PORT

TEST_HOST = TEST_HOST
TEST_PORT = TEST_PORT

SCRIPT_DIR = Path(__file__).parent.parent.parent.parent.joinpath(
    "curl_example/post_runs/cwltool").resolve()
RESOURCE_DIR: Path = Path(__file__).parent.parent.parent.parent.joinpath(
    "resources/cwltool").resolve()
REMOTE_URL: str = "https://raw.githubusercontent.com/ddbj/" +\
    "SAPPORO-service/master/tests/resources/cwltool/"

RESOURCE: Dict[str, Path] = {
    "FQ_1": RESOURCE_DIR.joinpath("ERR034597_1.small.fq.gz"),
    "FQ_2": RESOURCE_DIR.joinpath("ERR034597_2.small.fq.gz"),
    "WF": RESOURCE_DIR.joinpath("trimming_and_qc.cwl"),
    "WF_PACKED": RESOURCE_DIR.joinpath("trimming_and_qc_packed.cwl"),
    "WF_REMOTE": RESOURCE_DIR.joinpath("trimming_and_qc_remote.cwl"),
    "TOOL_1": RESOURCE_DIR.joinpath("fastqc.cwl"),
    "TOOL_2": RESOURCE_DIR.joinpath("trimmomatic_pe.cwl")
}
RESOURCE_REMOTE: Dict[str, str] = {
    "FQ_1": REMOTE_URL + "ERR034597_1.small.fq.gz",
    "FQ_2": REMOTE_URL + "ERR034597_2.small.fq.gz",
    "WF": REMOTE_URL + "trimming_and_qc.cwl",
    "WF_PACKED": REMOTE_URL + "trimming_and_qc_packed.cwl",
    "WF_REMOTE": REMOTE_URL + "trimming_and_qc_remote.cwl",
    "TOOL_1": REMOTE_URL + "fastqc.cwl",
    "TOOL_2": REMOTE_URL + "trimmomatic_pe.cwl",
}
