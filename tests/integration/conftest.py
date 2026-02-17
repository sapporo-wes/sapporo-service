"""Integration test infrastructure for sapporo-service.

Provides fixtures and helpers for submitting workflows via the WES API
and polling for completion. Requires a running sapporo instance
(e.g., via compose.dev.yml).
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from argon2 import PasswordHasher

if TYPE_CHECKING:
    from collections.abc import Generator

SAPPORO_HOST = "127.0.0.1"
SAPPORO_PORT = 1122
BASE_URL = f"http://{SAPPORO_HOST}:{SAPPORO_PORT}"
RESOURCES_DIR = Path(__file__).parent.parent / "resources"

SAPPORO_AUTH_PORT = 1123
AUTH_BASE_URL = f"http://{SAPPORO_HOST}:{SAPPORO_AUTH_PORT}"

TERMINAL_STATES = frozenset(
    {
        "COMPLETE",
        "EXECUTOR_ERROR",
        "SYSTEM_ERROR",
        "CANCELED",
    }
)

ALL_TERMINAL_STATES = TERMINAL_STATES | frozenset({"DELETED"})


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
    headers: dict[str, str] | None = None,
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

    res = client.post("/runs", data=data, files=files, headers=headers or {})
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
    headers: dict[str, str] | None = None,
) -> str:
    """Poll GET /runs/{run_id}/status until a terminal state is reached.

    Tolerates transient 5xx errors (e.g., race condition when state.txt
    is being written) by retrying on the next poll interval.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = client.get(f"/runs/{run_id}/status", headers=headers or {})
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


def wait_for_running(
    client: httpx.Client,
    run_id: str,
    *,
    timeout: int = 120,
    poll_interval: int = 2,
    headers: dict[str, str] | None = None,
) -> None:
    """Poll until the run reaches RUNNING state.

    Fails immediately if a terminal state is reached instead.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = client.get(f"/runs/{run_id}/status", headers=headers or {})
        if res.status_code >= 500:
            time.sleep(poll_interval)
            continue
        res.raise_for_status()
        state: str = res.json()["state"]
        if state == "RUNNING":
            return
        if state in TERMINAL_STATES:
            msg = f"Run {run_id} reached terminal state {state} before RUNNING"
            raise AssertionError(msg)
        time.sleep(poll_interval)

    msg = f"Run {run_id} did not reach RUNNING within {timeout}s"
    raise TimeoutError(msg)


def wait_for_state(
    client: httpx.Client,
    run_id: str,
    target_states: set[str],
    *,
    timeout: int = 300,
    poll_interval: int = 5,
    headers: dict[str, str] | None = None,
) -> str:
    """Poll until the run reaches one of the target states."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = client.get(f"/runs/{run_id}/status", headers=headers or {})
        if res.status_code >= 500:
            time.sleep(poll_interval)
            continue
        res.raise_for_status()
        state: str = res.json()["state"]
        if state in target_states:
            return state
        time.sleep(poll_interval)

    msg = f"Run {run_id} did not reach {target_states} within {timeout}s"
    raise TimeoutError(msg)


def get_run_log(
    client: httpx.Client,
    run_id: str,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """GET /runs/{run_id} and return the full run log."""
    res = client.get(f"/runs/{run_id}", headers=headers or {})
    res.raise_for_status()
    result: dict[str, Any] = res.json()
    return result


# === Auth helpers ===

_AUTH_USER1 = {"username": "testuser1", "password": "testpass1"}
_AUTH_USER2 = {"username": "testuser2", "password": "testpass2"}
_AUTH_SECRET_KEY = "integration_test_secret_key_1234567890abcdef"


def get_auth_token(client: httpx.Client, username: str, password: str) -> str:
    """POST /token and return the access_token string."""
    res = client.post("/token", data={"username": username, "password": password})
    res.raise_for_status()
    token: str = res.json()["access_token"]
    return token


def auth_headers(token: str) -> dict[str, str]:
    """Build Authorization header dict from a token."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def sapporo_auth_env() -> Generator[dict[str, Any]]:
    """Launch an auth-enabled sapporo instance on port 1123.

    Yields a dict with ``client``, ``user1``, ``user2`` keys.
    """
    ph = PasswordHasher()
    user1_hash = ph.hash(_AUTH_USER1["password"])
    user2_hash = ph.hash(_AUTH_USER2["password"])

    auth_config = {
        "auth_enabled": True,
        "idp_provider": "sapporo",
        "sapporo_auth_config": {
            "secret_key": _AUTH_SECRET_KEY,
            "expires_delta_hours": 24,
            "users": [
                {"username": _AUTH_USER1["username"], "password_hash": user1_hash},
                {"username": _AUTH_USER2["username"], "password_hash": user2_hash},
            ],
        },
        "external_config": {
            "idp_url": "https://dummy.example.com",
            "jwt_audience": "account",
            "client_mode": "public",
            "client_id": "dummy",
            "client_secret": "dummy",
        },
    }

    with tempfile.TemporaryDirectory(prefix="sapporo_auth_test_") as tmp_dir:
        auth_config_path = Path(tmp_dir) / "auth_config.json"
        auth_config_path.write_text(json.dumps(auth_config, indent=2))
        run_dir = Path(tmp_dir) / "runs"
        run_dir.mkdir()

        proc = subprocess.Popen(
            [
                "sapporo",
                "--port",
                str(SAPPORO_AUTH_PORT),
                "--auth-config",
                str(auth_config_path),
                "--run-dir",
                str(run_dir),
                "--debug",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            process_group=0,
        )

        # Wait for the server to be ready
        deadline = time.monotonic() + 30
        ready = False
        while time.monotonic() < deadline:
            try:
                with httpx.Client(base_url=AUTH_BASE_URL, timeout=5) as c:
                    r = c.get("/service-info")
                    if r.status_code in (200, 401):
                        ready = True
                        break
            except httpx.ConnectError:
                pass
            time.sleep(1)

        if not ready:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
            msg = f"Auth sapporo instance failed to start on port {SAPPORO_AUTH_PORT}"
            raise RuntimeError(msg)

        try:
            with httpx.Client(base_url=AUTH_BASE_URL, timeout=30) as client:
                yield {
                    "client": client,
                    "user1": _AUTH_USER1,
                    "user2": _AUTH_USER2,
                }
        finally:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=10)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait()
