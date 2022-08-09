#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=no-else-return
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from cwl_inputs_parser.utils import Inputs, as_uri
from cwl_inputs_parser.utils import \
    cwl_make_template as inputs_parser_make_template
from cwl_inputs_parser.utils import (download_file, is_remote_url,
                                     wf_location_to_inputs)
from cwl_utils.parser import cwl_version, load_document_by_string
from flask import abort
from schema_salad.utils import yaml_no_ts

from sapporo.model import ParseRequest, ParseResult


def parse_workflows(parse_request: ParseRequest) -> ParseResult:
    if parse_request["workflow_location"] is not None:
        if not is_remote_url(parse_request["workflow_location"]):
            abort(400, "Workflow location must be a remote URL")
        wf_content = download_file(parse_request["workflow_location"])
    else:
        wf_content = parse_request["workflow_content"]
    wf_location = parse_request["workflow_location"] or "."
    types_of_parsing = parse_request["types_of_parsing"] or [
        "workflow_type", "workflow_type_version"]

    wf_type = inspect_wf_type(wf_content, wf_location)
    wf_version = inspect_wf_version(wf_content, wf_type)

    inputs = None
    if wf_type == "CWL":
        if "make_template" in types_of_parsing:
            inputs = cwl_make_template(wf_content, wf_location)
        else:
            if "inputs" in types_of_parsing:
                try:
                    inputs = parse_cwl_inputs(
                        wf_content, wf_location)  # type: ignore
                except Exception:
                    inputs = cwl_make_template(wf_content, wf_location)
    else:
        if "inputs" in types_of_parsing or "make_template" in types_of_parsing:
            abort(
                400, f"Workflow type: `{wf_type}` is not supported parsing inputs or make template")

    parse_result: ParseResult = {
        "workflow_type": wf_type,  # type: ignore
        "workflow_type_version": wf_version,
        "inputs": inputs,
    }

    return parse_result


WF_TYPES = Literal["CWL", "WDL", "NFL", "SMK", "StreamFlow", "unknown"]


def inspect_wf_type(wf_content: str, wf_location: str) -> WF_TYPES:
    wf_type = check_by_shebang(wf_content)
    if wf_type != "unknown":
        return wf_type

    wf_type = check_by_cwl_utils(wf_content, wf_location)
    if wf_type != "unknown":
        return wf_type

    wf_type = check_by_regexp(wf_content)
    if wf_type != "unknown":
        return wf_type

    return "unknown"


def check_by_shebang(wf_content: str) -> WF_TYPES:
    first_line = wf_content.split("\n")[0]
    if first_line.startswith("#!"):
        if "cwl" in first_line:
            return "CWL"
        elif "nextflow" in first_line:
            return "NFL"
        elif "snakemake" in first_line:
            return "SMK"
        elif "cromwell" in first_line:
            return "WDL"
        elif "streamflow" in first_line:
            return "StreamFlow"

    return "unknown"


def check_by_cwl_utils(wf_content: str, wf_location: str) -> Literal["CWL", "unknown"]:
    try:
        load_document_by_string(wf_content, as_uri(wf_location))
        return "CWL"
    except Exception:
        return "unknown"


PATTERN_WDL = re.compile(r"^(workflow|task) \w* \{$")
PATTERN_SMK = re.compile(r"^rule \w*:$")
PATTERN_NFL = re.compile(r"^process \w* \{$")


def check_by_regexp(wf_content: str) -> WF_TYPES:
    for line in wf_content.split("\n"):
        if PATTERN_WDL.match(line):
            return "WDL"
        elif PATTERN_SMK.match(line):
            return "SMK"
        elif PATTERN_NFL.match(line):
            return "NFL"

    return "unknown"


def inspect_wf_version(wf_content: str, wf_type: WF_TYPES) -> str:
    wf_version = "unknown"
    if wf_type == "CWL":
        wf_version = inspect_cwl_version(wf_content)
    elif wf_type == "WDL":
        wf_version = inspect_wdl_version(wf_content)
    elif wf_type == "NFL":
        wf_version = inspect_nfl_version(wf_content)
    elif wf_type == "SMK":
        wf_version = inspect_smk_version()
    elif wf_type == "StreamFlow":
        wf_version = inspect_streamflow_version(wf_content)

    return wf_version


def inspect_cwl_version(wf_content: str) -> str:
    """
    https://www.commonwl.org/v1.2/CommandLineTool.html#CWLVersion
    """
    default_cwl_version = "v1.0"

    yaml = yaml_no_ts()
    yaml_obj = yaml.load(wf_content)

    return cwl_version(yaml_obj) or default_cwl_version


PATTERN_WDL_VERSION = re.compile(r"^version \d\.\d$")


def inspect_wdl_version(wf_content: str) -> str:
    default_wdl_version = "1.0"

    for line in wf_content.split("\n"):
        if PATTERN_WDL_VERSION.match(line):
            return line.split(" ")[1]

    return default_wdl_version


def inspect_nfl_version(wf_content: str) -> str:
    default_nfl_version = "1.0"

    for line in wf_content.split("\n"):
        if line == "nextflow.enable.dsl=2":
            return "DSL2"

    return default_nfl_version


def inspect_smk_version() -> str:
    default_smk_version = "1.0"

    return default_smk_version


def inspect_streamflow_version(wf_content: str) -> str:
    default_streamflow_version = "v1.0"

    yaml = yaml_no_ts()
    yaml_obj = yaml.load(wf_content)

    return yaml_obj['version'] or default_streamflow_version


def parse_cwl_inputs(wf_content: str, wf_location: str) -> List[Dict[str, Any]]:
    if is_remote_url(wf_location):
        inputs = wf_location_to_inputs(wf_location)
    else:
        wf_obj = load_document_by_string(wf_content, uri=Path.cwd().as_uri())
        inputs = Inputs(wf_obj)

    return inputs.as_dict()  # type: ignore


def cwl_make_template(wf_content: str, wf_location: str) -> Optional[str]:
    inputs: Optional[str] = None
    if is_remote_url(wf_location):
        inputs = inputs_parser_make_template(wf_location)
    else:
        with tempfile.NamedTemporaryFile(suffix=".cwl") as temp_file:
            temp_file.write(wf_content.encode("utf-8"))
            temp_file.flush()
            inputs = inputs_parser_make_template(temp_file.name)

    return inputs
