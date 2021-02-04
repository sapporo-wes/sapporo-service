#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path
from typing import Dict

from ...conftest import TEST_HOST, TEST_PORT

TEST_HOST = TEST_HOST
TEST_PORT = TEST_PORT

SCRIPT_DIR = Path(__file__).parent.parent.parent.parent.joinpath(
    "curl_example/post_runs/cromwell").resolve()
RESOURCE_DIR: Path = Path(__file__).parent.parent.parent.parent.joinpath(
    "resources/cromwell/dockstore-tool-bamstats").resolve()

RESOURCE: Dict[str, Path] = {
    "CWL_WF": RESOURCE_DIR.joinpath("Dockstore.cwl"),
    "CWL_PARAMS": RESOURCE_DIR.joinpath("test.json"),
    "WDL_WF": RESOURCE_DIR.joinpath("Dockstore.wdl"),
    "WDL_PARAMS": RESOURCE_DIR.joinpath("test.wdl.json"),
    "DATA": RESOURCE_DIR.joinpath("rna.SRR948778.bam"),
}
