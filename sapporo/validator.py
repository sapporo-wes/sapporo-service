#!/usr/bin/env python3
# coding: utf-8
import json
from typing import List, Optional, Tuple, cast

from flask import abort, current_app, request
from werkzeug.datastructures import FileStorage

from sapporo.model import AttachedFile, ParseRequest, RunRequest, WorkflowTypes
from sapporo.model.factory import (generate_executable_workflows,
                                   generate_service_info)
from sapporo.parser import parse_workflows
from sapporo.run import (glob_all_run_ids, resolve_content_path,
                         sapporo_endpoint, secure_filepath)

EXPECTED_PARSING_TYPES = [
    "workflow_type",
    "workflow_type_version",
    "inputs",
    "make_template",
]


def validate_post_parse_workflows() -> ParseRequest:
    parse_request: ParseRequest = {
        "workflow_content": request.form.get("workflow_content", None),
        "workflow_location": request.form.get("workflow_location", None),
        "types_of_parsing": request.form.getlist("types_of_parsing") or ["workflow_type", "workflow_type_version"],
    }
    if parse_request["types_of_parsing"] is not None:
        for _type in parse_request["types_of_parsing"]:
            if _type not in EXPECTED_PARSING_TYPES:
                abort(400, f"Parsing type `{_type}` is not supported.")
    if parse_request["workflow_content"] is None and parse_request["workflow_location"] is None:
        abort(400, "Please specify either `workflow_content` or `workflow_location`.")
    if parse_request["workflow_content"] is not None and parse_request["workflow_location"] is not None:
        abort(400, "Please specify either `workflow_content` or `workflow_location`, not both.")

    return parse_request


def validate_get_runs() -> None:
    if current_app.config["GET_RUNS"] is False:
        abort(403, "The endpoint `GET /runs` is unavailable. The service provider has disallowed requests to this endpoint.")


def validate_run_request(run_id: str) -> RunRequest:
    # Fields: do not require validation
    wf_params = request.form.get("workflow_params", None)
    wf_engine_params = request.form.get("workflow_engine_parameters", None)
    tags = request.form.get("tags", None)

    # Fields: require validation, but not related to the registered mode
    wf_engine = request.form.get("workflow_engine", None)
    if wf_engine is None:  # for compatibility with the sapporo-wes 1.0.1, will be deprecated in the future (TODO)
        wf_engine = request.form.get("workflow_engine_name", None)
    __wf_engine_version = request.form.get("workflow_engine_version", None)  # added in WES 1.1, but not used in current impl.
    wf_attachment_str = request.form.get("workflow_attachment", None)
    wf_attachment_files = request.files.getlist("workflow_attachment")
    wf_engine = validate_wf_engine(wf_engine)
    wf_attachment = validate_wf_attachment(run_id, wf_attachment_str, wf_attachment_files)

    # Fields: require validation, related to the registered mode
    wf_url = request.form.get("workflow_url", None)
    wf_name = request.form.get("workflow_name", None)
    wf_type = request.form.get("workflow_type", None)
    wf_type_version = request.form.get("workflow_type_version", None)

    if wf_name is not None:  # registered mode request
        wf_url, wf_type, wf_type_version, wf_attachment = validate_wf_docs_with_registered_wf(wf_name, wf_attachment)
    else:  # normal mode request
        validate_registered_only_mode()
        wf_type, wf_type_version = validate_wf_docs_with_no_registered_wf(wf_url, wf_type, wf_type_version)
        wf_url = cast(str, wf_url)

    validate_workflow_type(wf_type, wf_type_version)
    wf_type = cast(WorkflowTypes, wf_type)

    # Meta characters validation
    validate_meta_characters("workflow_url", wf_url)
    if wf_engine_params is not None:
        try:
            wf_engine_params_obj = json.loads(wf_engine_params)
            if isinstance(wf_engine_params_obj, list):
                for val in wf_engine_params_obj:
                    validate_meta_characters("workflow_engine_parameters", val)
            elif isinstance(wf_engine_params_obj, dict):
                for key, val in wf_engine_params_obj.items():
                    validate_meta_characters("workflow_engine_parameters", key)
                    validate_meta_characters("workflow_engine_parameters", val)
            else:
                abort(400, "`workflow_engine_parameters` must be a list or a dictionary.")
        except json.JSONDecodeError:
            abort(400, "`workflow_engine_parameters` is not a valid JSON.")

    return {
        "workflow_params": wf_params,
        "workflow_type": wf_type,
        "workflow_type_version": wf_type_version,
        "tags": tags,
        "workflow_engine": wf_engine,
        "workflow_engine_version": __wf_engine_version if __wf_engine_version is not None else "",
        "workflow_engine_parameters": wf_engine_params,
        "workflow_url": wf_url,
        "workflow_name": wf_name,
        "workflow_attachment": json.dumps(wf_attachment),
    }


def validate_wf_engine(wf_engine: Optional[str]) -> str:
    if wf_engine is None:
        abort(400, "Workflow engine is required.")
    service_info = generate_service_info()
    wf_engines = list(service_info["workflow_engine_versions"].keys())
    if wf_engine not in wf_engines:
        abort(400, f"Workflow engine `{wf_engine}` is not supported.")

    return wf_engine


def validate_registered_only_mode() -> None:
    if current_app.config["REGISTERED_ONLY_MODE"]:
        abort(403, "The sapporo-service is currently running in registered-only mode. The `POST /runs` endpoint is unavailable to specify `workflow_url`.")


def validate_wf_attachment(run_id: str, wf_attachment_str: Optional[str], wf_attachment_files: List[FileStorage]) -> List[AttachedFile]:
    wf_attachment: List[AttachedFile] = []
    if current_app.config["WORKFLOW_ATTACHMENT"]:
        if wf_attachment_str is not None:
            try:
                wf_attachment_obj = json.loads(wf_attachment_str)
                try:
                    for attached_file in wf_attachment_obj:
                        wf_attachment.append({
                            "file_name": str(attached_file["file_name"]),
                            "file_url": str(attached_file["file_url"]),
                        })
                except KeyError:
                    abort(400, "`workflow_attachment` must be a list of `AttachedFile`.")
            except json.JSONDecodeError:
                abort(400, "`workflow_attachment` is invalid.")
        if len(wf_attachment_files):
            exe_dir = resolve_content_path(run_id, "exe_dir")
            endpoint = sapporo_endpoint()
            base_remote_url = f"{endpoint}/runs/{run_id}/data/"
            for file in wf_attachment_files:
                if file.filename is None:
                    continue
                file_name = secure_filepath(file.filename)
                file_path = exe_dir.joinpath(file_name).resolve()
                wf_attachment.append({
                    "file_name": str(file_name),
                    "file_url": base_remote_url + str(file_path.relative_to(exe_dir.parent))
                })
    else:
        if wf_attachment_str is not None or len(wf_attachment_files) != 0:
            abort(400, "`workflow_attachment` is invalid because the sapporo-service is running in disable-workflow-attachment mode.")

    return wf_attachment


def validate_wf_docs_with_registered_wf(wf_name: str, wf_attachment: List[AttachedFile]) -> Tuple[str, str, str, List[AttachedFile]]:
    executable_wfs = generate_executable_workflows()
    wf_names = [wf["workflow_name"] for wf in executable_wfs]
    if wf_name not in wf_names:
        abort(400, f"Workflow name `{wf_name}` does not exist.")
    wf = executable_wfs[wf_names.index(wf_name)]
    wf_url = wf["workflow_url"]
    wf_type = wf["workflow_type"]
    wf_type_version = wf["workflow_type_version"]
    wf_attachment_names = [f["file_name"] for f in wf_attachment]
    for file in wf["workflow_attachment"]:
        if file["file_name"] not in wf_attachment_names:
            wf_attachment.append(file)

    return wf_url, wf_type, wf_type_version, wf_attachment


def validate_wf_docs_with_no_registered_wf(wf_url: Optional[str], wf_type: Optional[str], wf_type_version: Optional[str]) -> Tuple[str, str]:
    if wf_url is None:
        abort(400, "`workflow_url` is required.")
    if wf_type is None or wf_type_version is None:
        try:
            parse_result = parse_workflows({
                "workflow_content": None,
                "workflow_location": wf_url,
                "types_of_parsing": ["workflow_type", "workflow_type_version"],
            })
            wf_type = wf_type or parse_result["workflow_type"]
            wf_type_version = wf_type_version or parse_result["workflow_type_version"]
        except Exception:  # pylint: disable=broad-except
            abort(400, "`workflow_type` and `workflow_type_version` are required.")

    return wf_type, wf_type_version  # type: ignore


def validate_workflow_type(wf_type: str, wf_type_version: str) -> None:
    service_info = generate_service_info()
    wf_type_versions = service_info["workflow_type_versions"]
    available_wf_types: List[str] = list(map(str, wf_type_versions.keys()))
    if wf_type not in available_wf_types:
        abort(400, f"Invalid wf type `{wf_type}`. Please use one of the available types.")
    available_wf_versions = wf_type_versions[wf_type]["workflow_type_version"]  # type: ignore
    if wf_type_version not in available_wf_versions:
        abort(
            400, f"Invalid workflow type version `{wf_type_version}` for the workflow type `{wf_type}`. Please use one of the available versions.")


def validate_run_id(run_id: str) -> None:
    all_run_ids: List[str] = glob_all_run_ids()
    if run_id not in all_run_ids:
        abort(404, f"Run ID `{run_id}` does not exist. Please provide a valid run ID.")


def validate_meta_characters(_type: str, content: str) -> None:
    """\
    This function checks the validity of the string that will be evaluated in the 'eval'
    command within run.sh. The string could be of the type 'workflow_url',
    'workflow_engine', or 'workflow_engine_params'. If any of these strings contain
    characters from the list of prohibited characters below, the operation will be aborted.

    This function is invoked as shown below in the POST /runs endpoint:

    validate_meta_characters("workflow_engine_params", joined_params)
    validate_meta_characters("workflow_url", run_request["workflow_url"])
    validate_meta_characters("workflow_engine", run_request["workflow_engine"])
    """
    prohibited_characters = [";", "!", "?", "(", ")", "[", "]", "{", "}", "*", "\\", "&", r"`", "^", "<", ">", "|", "$"]
    for char in content:
        if char in prohibited_characters:
            abort(400, f"The `{_type}` contains a prohibited character `{char}`. Please remove this character.")
