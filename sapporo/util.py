#!/usr/bin/env python3
# coding: utf-8
import collections
import json
import os
from pathlib import Path, PurePath
from typing import Any, Dict, Iterable, List, Union
from unicodedata import normalize
from uuid import uuid4

from flask import abort, current_app, request
from werkzeug.utils import _filename_ascii_strip_re  # type: ignore
from werkzeug.utils import _windows_device_files  # type: ignore

from sapporo.const import RUN_DIR_STRUCTURE
from sapporo.type import ServiceInfo, State, Workflow


def generate_service_info() -> ServiceInfo:
    with current_app.config["SERVICE_INFO"].open(mode="r") as f:
        service_info: ServiceInfo = json.load(f)

    service_info["supported_wes_versions"] = ["sapporo-wes-1.0.0"]
    service_info["system_state_counts"] = count_system_state()  # type: ignore
    service_info["tags"]["debug"] = current_app.config["DEBUG"]
    service_info["tags"]["get_runs"] = current_app.config["GET_RUNS"]
    service_info["tags"]["workflow_attachment"] = \
        current_app.config["WORKFLOW_ATTACHMENT"]
    service_info["tags"]["registered_only_mode"] = \
        current_app.config["REGISTERED_ONLY_MODE"]

    with current_app.config["EXECUTABLE_WORKFLOWS"].open(mode="r") as f:
        executable_workflows: List[Workflow] = json.load(f)
    service_info["executable_workflows"] = executable_workflows

    return service_info


def generate_run_id() -> str:
    return str(uuid4())


def get_run_dir(run_id: str) -> Path:
    run_base_dir: Path = current_app.config["RUN_DIR"]

    return run_base_dir.joinpath(run_id[:2]).joinpath(run_id).resolve()


def get_path(run_id: str, key: str) -> Path:
    run_dir: Path = get_run_dir(run_id)

    return run_dir.joinpath(RUN_DIR_STRUCTURE[key])


def get_all_run_ids() -> List[str]:
    run_base_dir: Path = current_app.config["RUN_DIR"]
    run_requests: List[Path] = \
        list(run_base_dir.glob(f"**/{RUN_DIR_STRUCTURE['run_request']}"))
    run_ids: List[str] = \
        [run_request.parent.name for run_request in run_requests]

    return run_ids


def get_state(run_id: str) -> State:
    try:
        with get_path(run_id, "state").open(mode="r") as f:
            str_state: str = \
                [line for line in f.read().splitlines() if line != ""][0]
        return State[str_state]
    except Exception:
        return State.UNKNOWN


def count_system_state() -> Dict[str, int]:
    run_ids: List[str] = get_all_run_ids()
    count: Dict[str, int] = \
        dict(collections.Counter(
            [get_state(run_id).name for run_id in run_ids]))

    return count


def write_file(run_id: str, file_type: str, content: str) -> None:
    file: Path = get_path(run_id, file_type)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open(mode="w") as f:
        f.write(content)


def read_file(run_id: str, file_type: str) -> Any:
    json_file_type = ["run_request", "outputs", "wf_params"]
    oneline_txt_file_type = ["state", "start_time", "end_time",
                             "exit_code", "pid", "wf_engine_params", "cmd"]
    log_file_type = ["stdout", "stderr", "task_logs"]
    if file_type not in json_file_type + oneline_txt_file_type + log_file_type:
        return None
    file: Path = get_path(run_id, file_type)
    if file.exists() is False:
        return None
    with file.open(mode="r") as f:
        if file_type in json_file_type:
            return json.load(f)
        elif file_type in oneline_txt_file_type:
            return f.read().splitlines()[0]
        elif file_type in log_file_type:
            return f.read()


def dump_outputs_list(inputted_run_dir: str) -> None:
    run_dir: Path = Path(inputted_run_dir).resolve()
    run_id = run_dir.name
    with run_dir.joinpath(
            RUN_DIR_STRUCTURE["sapporo_config"]).open(mode="r") as f:
        sapporo_config = json.load(f)
    base_remote_url = \
        f"{sapporo_config['sapporo_endpoint']}/runs/{run_id}/data/"
    outdir_path: Path = run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"])
    output_files: List[Path] = sorted(list(walk_all_files(outdir_path)))
    outputs = []
    for output_file in output_files:
        outputs.append({
            "file_name": output_file.name,
            "file_url":
                f"{base_remote_url}{str(output_file.relative_to(run_dir))}"
        })
    with run_dir.joinpath(RUN_DIR_STRUCTURE["outputs"]).open(mode="w") as f:
        f.write(json.dumps(outputs, indent=2))


def walk_all_files(dir: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(dir):
        for file in files:
            yield Path(root).joinpath(file)


def get_workflow(workflow_name: str) -> Workflow:
    with current_app.config["EXECUTABLE_WORKFLOWS"].open(mode="r") as f:
        executable_workflows: List[Workflow] = json.load(f)
    for wf in executable_workflows:
        if wf["workflow_name"] == workflow_name:
            return wf

    abort(404,
          f"The workflow_name: {workflow_name} you requested doesn't "
          "exist. Please request `GET /service-info` again and check "
          "the registered executable workflows.")


def validate_wf_type(wf_type: str, wf_type_version: str) -> None:
    service_info: ServiceInfo = generate_service_info()
    wf_type_versions = service_info["workflow_type_versions"]

    available_wf_types: List[str] = list(map(str, wf_type_versions.keys()))
    if wf_type not in available_wf_types:
        abort(400,
              f"{wf_type}, the workflow_type specified in the "
              f"request, is not included in {available_wf_types}, "
              "the available workflow_types.")

    available_wf_versions: List[str] = \
        list(map(str, wf_type_versions[wf_type]["workflow_type_version"]))
    if wf_type_version not in available_wf_versions:
        abort(400,
              f"{wf_type_version}, the workflow_type_version specified in "
              f"the request, is not included in {available_wf_versions}, "
              "the available workflow_type_versions.")


def secure_filepath(filepath: str) -> Path:
    """
    We know `werkzeug.secure_filename()`.
    However, this function cannot represent the dir structure,

    >>> secure_filename("../../../etc/passwd")
    'etc_passwd'

    Thus, it is incompatible with workflow engines such as snakemake.
    Therefore, We implemented this by referring to `werkzeug.secure_filename()`

    Please check `tests/unit_test/test_secure_filepath.py`

    Reference of `PurePath.parts`:
    >> > PurePath("/").parts
    ('/',)
    >> > PurePath("//").parts
    ('//',)
    >> > PurePath("/foo/bar").parts
    ('/', 'foo', 'bar')
    >> > PurePath("foo/bar").parts
    ('foo', 'bar')
    >> > PurePath("/foo/bar/").parts
    ('/', 'foo', 'bar')
    >> > PurePath("./foo/bar/").parts
    ('foo', 'bar')
    >> > PurePath("/../../foo/bar//").parts
    ('/', '..', '..', 'foo', 'bar')
    >> > PurePath("/../.../foo/bar//").parts
    ('/', '..', '...', 'foo', 'bar')
    """
    ascii_filepath = \
        normalize("NFKD", filepath).encode("ascii", "ignore").decode("ascii")
    pure_path = PurePath(ascii_filepath)
    nodes = []
    for node in pure_path.parts:
        # Change space to underbar
        node = "_".join(node.split())
        # Change [^A-Za-z0-9_.-] to empty.
        node = str(_filename_ascii_strip_re.sub("", node))
        node = node.strip("._")
        if node not in ["", ".", ".."]:
            nodes.append(node)

    path = Path("/".join([str(node) for node in nodes]))

    if (
        os.name == "nt"
        and str(path)
        and str(path).split(".")[0].upper() in _windows_device_files
    ):
        path = Path("_" + str(path))

    return path


def path_hierarchy(original_path: Path, dir_path: Path) -> Any:
    hierarchy: Dict[str, Any] = {
        "type": "directory",
        "name": dir_path.name,
        "path": str(dir_path.relative_to(original_path)),
    }

    try:
        hierarchy["children"] = [
            path_hierarchy(original_path, dir_path.joinpath(child))
            for child in dir_path.iterdir()
        ]
    except Exception:
        hierarchy["type"] = "file"

    return hierarchy


def str2bool(val: Union[str, bool]) -> bool:
    if isinstance(val, bool):
        return val
    if val.lower() in ["true", "yes", "y"]:
        return True
    if val.lower() in ["false", "no", "n"]:
        return False

    return bool(val)


def dump_sapporo_config(run_id: str) -> str:
    host = request.host_url.strip("/")
    url_prefix = current_app.config['URL_PREFIX'].strip("/")
    endpoint = f"{host}/{url_prefix}".strip("/")

    return json.dumps({
        "get_runs": current_app.config["GET_RUNS"],
        "workflow_attachment": current_app.config["WORKFLOW_ATTACHMENT"],
        "registered_only_mode": current_app.config["REGISTERED_ONLY_MODE"],
        "service_info": str(current_app.config["SERVICE_INFO"]),
        "executable_workflows":
            str(current_app.config["EXECUTABLE_WORKFLOWS"]),
        "run_sh": str(current_app.config["RUN_SH"]),
        "url_prefix": current_app.config["URL_PREFIX"],
        "sapporo_endpoint": endpoint
    }, indent=2)
