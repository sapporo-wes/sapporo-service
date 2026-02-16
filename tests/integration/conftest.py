"""Integration test infrastructure for sapporo-service.

Provides fixtures and helpers for submitting workflows via the WES API
and polling for completion. Requires a running sapporo instance
(e.g., via compose.dev.yml).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

SAPPORO_HOST = "127.0.0.1"
SAPPORO_PORT = 1122
BASE_URL = f"http://{SAPPORO_HOST}:{SAPPORO_PORT}"
RESOURCES_DIR = Path(__file__).parent.parent / "resources"

TERMINAL_STATES = frozenset(
    {
        "COMPLETE",
        "EXECUTOR_ERROR",
        "SYSTEM_ERROR",
        "CANCELED",
    }
)


@pytest.fixture(scope="session")
def sapporo_client() -> Generator[httpx.Client]:
    """Httpx client pointing to a running sapporo instance.

    Assumes sapporo is already running (via compose.dev.yml or direct).
    """
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        res = client.get("/service-info")
        res.raise_for_status()
        yield client


def submit_workflow(
    client: httpx.Client,
    *,
    wf_type: str,
    wf_type_version: str,
    wf_engine: str,
    wf_url: str,
    params_file: Path,
    attachments: list[Path],
    engine_params: str | None = None,
) -> str:
    """POST /runs with multipart form-data and return run_id."""
    files = [
        (
            "workflow_attachment",
            (attachment.name, attachment.read_bytes(), "application/octet-stream"),
        )
        for attachment in attachments
    ]

    data: dict[str, str] = {
        "workflow_type": wf_type,
        "workflow_type_version": wf_type_version,
        "workflow_engine": wf_engine,
        "workflow_url": wf_url,
        "workflow_params": params_file.read_text(),
    }
    if engine_params is not None:
        data["workflow_engine_parameters"] = engine_params

    res = client.post("/runs", data=data, files=files)
    res.raise_for_status()
    body = res.json()
    run_id: str = body["run_id"]
    return run_id


def wait_for_completion(
    client: httpx.Client,
    run_id: str,
    *,
    timeout: int = 300,
    poll_interval: int = 5,
) -> str:
    """Poll GET /runs/{run_id}/status until a terminal state is reached.

    Tolerates transient 5xx errors (e.g., race condition when state.txt
    is being written) by retrying on the next poll interval.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = client.get(f"/runs/{run_id}/status")
        if res.status_code >= 500:
            time.sleep(poll_interval)
            continue
        res.raise_for_status()
        state: str = res.json()["state"]
        if state in TERMINAL_STATES:
            return state
        time.sleep(poll_interval)

    msg = f"Run {run_id} did not reach terminal state within {timeout}s"
    raise TimeoutError(msg)


def get_run_log(client: httpx.Client, run_id: str) -> dict[str, Any]:
    """GET /runs/{run_id} and return the full run log."""
    res = client.get(f"/runs/{run_id}")
    res.raise_for_status()
    result: dict[str, Any] = res.json()
    return result
