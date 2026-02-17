"""File I/O operations for run directories.

Extracted from run.py to break circular imports between
run.py, factory.py, and database.py.
"""

import json
import shlex
from pathlib import Path
from typing import Any

from sapporo.config import RUN_DIR_STRUCTURE, RunDirStructureKeys, get_config
from sapporo.schemas import RunRequest, State
from sapporo.utils import sapporo_version


def resolve_run_dir(run_id: str) -> Path:
    run_dir_base = get_config().run_dir

    return run_dir_base.joinpath(run_id[:2]).joinpath(run_id).resolve()


def resolve_content_path(run_id: str, key: RunDirStructureKeys) -> Path:
    return resolve_run_dir(run_id).joinpath(RUN_DIR_STRUCTURE[key])


def write_file(run_id: str, key: RunDirStructureKeys, content: Any) -> None:
    file = resolve_content_path(run_id, key)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open(mode="w", encoding="utf-8") as f:
        if file.suffix == ".json":
            if key == "wf_params" and isinstance(content, str):
                pass
            else:
                content = json.dumps(content, indent=2)
        elif key == "state":
            content = content.value
        else:
            content = str(content)
        f.write(content)


def read_file(run_id: str, key: RunDirStructureKeys) -> Any:
    if key == "state":
        return read_state(run_id)

    if "dir" in key:
        return None
    file_path = resolve_content_path(run_id, key)
    if file_path.exists() is False:
        return None

    with file_path.open(mode="r", encoding="utf-8") as f:
        content = f.read().strip()
        # Special handling for specific keys
        if key == "run_request":
            return RunRequest.model_validate_json(content)
        if key == "cmd":
            return shlex.split(content)
        if key in ["start_time", "end_time", "stdout", "stderr", "username"]:
            return content
        if key in ["pid", "exit_code"]:
            return int(content)
        if key == "ro_crate":
            return json.loads(content)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content


def read_state(run_id: str) -> State:
    try:
        with resolve_content_path(run_id, "state").open(mode="r", encoding="utf-8") as f:
            return State(f.read().strip())
    except FileNotFoundError:
        return State("UNKNOWN")


def glob_all_run_ids() -> list[str]:
    return [run_dir.parent.name for run_dir in get_config().run_dir.glob(f"*/*/{RUN_DIR_STRUCTURE['run_request']}")]


def dump_runtime_info(run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "sapporo_version": sapporo_version(),
        "base_url": get_config().base_url,
    }
