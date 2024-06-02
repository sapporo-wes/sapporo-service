from datetime import datetime, timezone
from pathlib import Path
from typing import Union

import pkg_resources


def str2bool(val: Union[str, bool]) -> bool:
    if isinstance(val, bool):
        return val
    if val.lower() in ["true", "yes", "y"]:
        return True
    if val.lower() in ["false", "no", "n"]:
        return False

    return bool(val)


def inside_docker() -> bool:
    return Path("/.dockerenv").exists()


def now_str() -> str:
    """
    Return the current time in RFC 3339 format. (e.g., "2022-01-01T00:00:00Z")
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sapporo_version() -> str:
    return pkg_resources.get_distribution("sapporo").version
