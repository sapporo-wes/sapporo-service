#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path

RESOURCE_DIR: Path = Path(__file__).parent.joinpath("resources").resolve()

FQ_1: Path = RESOURCE_DIR.joinpath("ERR034597_1.small.fq.gz")
FQ_2: Path = RESOURCE_DIR.joinpath("ERR034597_2.small.fq.gz")
CWL_WF: Path = RESOURCE_DIR.joinpath("trimming_and_qc.cwl")
CWL_TOOL_1: Path = RESOURCE_DIR.joinpath("fastqc.cwl")
CWL_TOOL_2: Path = RESOURCE_DIR.joinpath("trimmomatic_pe.cwl")

REMOTE_LOCATION: str = "https://raw.githubusercontent.com/ddbj/" +\
    "SAPPORO-service/master/tests/resources/"

REMOTE_FQ_1: str = REMOTE_LOCATION + "ERR034597_1.small.fq.gz"
REMOTE_FQ_2: str = REMOTE_LOCATION + "ERR034597_2.small.fq.gz"
REMOTE_CWL_WF: str = REMOTE_LOCATION + "trimming_and_qc.cwl"
REMOTE_CWL_WF_REMOTE: str = REMOTE_LOCATION + "trimming_and_qc_remote.cwl"
REMOTE_CWL_TOOL_1: str = REMOTE_LOCATION + "fastqc.cwl"
REMOTE_CWL_TOOL_2: str = REMOTE_LOCATION + "trimmomatic_pe.cwl"
