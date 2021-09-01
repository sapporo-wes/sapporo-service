#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path
from typing import Dict

from ...conftest import TEST_HOST, TEST_PORT

TEST_HOST = TEST_HOST
TEST_PORT = TEST_PORT

SCRIPT_DIR = Path(__file__).parent.parent.parent.parent.joinpath(
    "curl_example/post_runs/snakemake").resolve()
RESOURCE_DIR: Path = Path(__file__).parent.parent.parent.parent.joinpath(
    "resources/snakemake").resolve()
REMOTE_URL: str = "https://raw.githubusercontent.com/ddbj/" +\
    "sapporo-service/main/tests/resources/snakemake/"

RESOURCE: Dict[str, Path] = {
    "WORKFLOW": RESOURCE_DIR.joinpath("Snakefile"),
    "SCRIPT_1": RESOURCE_DIR.joinpath("scripts/plot-quals.py"),
    "ENV_1": RESOURCE_DIR.joinpath("envs/stats.yaml"),
    "ENV_2": RESOURCE_DIR.joinpath("envs/calling.yaml"),
    "ENV_3": RESOURCE_DIR.joinpath("envs/mapping.yaml"),
    "SAMPLE_1": RESOURCE_DIR.joinpath("data/samples/A.fastq"),
    "SAMPLE_2": RESOURCE_DIR.joinpath("data/samples/B.fastq"),
    "SAMPLE_3": RESOURCE_DIR.joinpath("data/samples/C.fastq"),
    "SAMPLE_4": RESOURCE_DIR.joinpath("data/genome.fa"),
    "SAMPLE_5": RESOURCE_DIR.joinpath("data/genome.fa.amb"),
    "SAMPLE_6": RESOURCE_DIR.joinpath("data/genome.fa.fai"),
    "SAMPLE_7": RESOURCE_DIR.joinpath("data/genome.fa.sa"),
    "SAMPLE_8": RESOURCE_DIR.joinpath("data/genome.fa.pac"),
    "SAMPLE_9": RESOURCE_DIR.joinpath("data/genome.fa.ann"),
    "SAMPLE_10": RESOURCE_DIR.joinpath("data/genome.fa.bwt")
}
