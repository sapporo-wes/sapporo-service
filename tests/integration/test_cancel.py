"""Integration tests for run cancellation lifecycle."""

from __future__ import annotations

import subprocess
import time
from typing import TYPE_CHECKING

import pytest

from tests.integration.conftest import (
    RESOURCES_DIR,
    get_run_log,
    submit_workflow,
    wait_for_completion,
    wait_for_running,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import httpx

pytestmark = pytest.mark.integration

CWL_DIR = RESOURCES_DIR / "cwl"
NF_DIR = RESOURCES_DIR / "nextflow"
WDL_DIR = RESOURCES_DIR / "wdl"


def _step_containers(image: str) -> set[str]:
    """Ids of the running containers that were started from image."""
    out = subprocess.run(
        ["docker", "ps", "--filter", f"ancestor={image}", "--format", "{{.ID}}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return set(out.split())


def _wait_until(predicate: Callable[[], bool], timeout: float, interval: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


# Engines that start workflow steps as containers through the Docker socket, with the image of the
# sleep step. Cromwell and Nextflow run their job scripts with bash inside the step container, so
# their sleep workflows use an image that has bash.
_CWL_SLEEP = ("CWL", "v1.2", "sleep.cwl", CWL_DIR / "sleep_params.json", [CWL_DIR / "sleep.cwl"], "alpine:3.20")
STEP_CONTAINER_CASES = [
    pytest.param("cwltool", *_CWL_SLEEP, id="cwltool"),
    pytest.param(
        "toil",
        *_CWL_SLEEP,
        id="toil",
        marks=pytest.mark.xfail(
            strict=True,
            reason="toil stops its worker process on SIGTERM but leaves the container that the worker started running",
        ),
    ),
    pytest.param(
        "ep3",
        *_CWL_SLEEP,
        id="ep3",
        marks=pytest.mark.xfail(
            strict=True,
            reason="ep3 does not act on SIGTERM; the engine container is killed after the grace period and its step container keeps running",
        ),
    ),
    pytest.param(
        "streamflow",
        *_CWL_SLEEP,
        id="streamflow",
        marks=pytest.mark.xfail(
            strict=True,
            reason="streamflow does not act on SIGTERM; the engine container is killed after the grace period and its step container keeps running",
        ),
    ),
    pytest.param(
        "nextflow",
        "NFL",
        "DSL2",
        "sleep.nf",
        NF_DIR / "sleep_params.json",
        [NF_DIR / "sleep.nf", NF_DIR / "nextflow.config"],
        "ubuntu:24.04",
        id="nextflow",
    ),
    pytest.param(
        "cromwell",
        "WDL",
        "1.0",
        "sleep.wdl",
        WDL_DIR / "sleep_params.json",
        [WDL_DIR / "sleep.wdl"],
        "ubuntu:24.04",
        id="cromwell",
    ),
]


class TestCancelRunning:
    def test_cancel_running_cwltool(self, sapporo_client: httpx.Client) -> None:
        """Cancel a RUNNING sleep workflow -> CANCELED with exit_code 138."""
        run_id = submit_workflow(
            sapporo_client,
            wf_type="CWL",
            wf_type_version="v1.2",
            wf_engine="cwltool",
            wf_url="sleep.cwl",
            params_file=CWL_DIR / "sleep_params.json",
            attachments=[CWL_DIR / "sleep.cwl"],
        )

        wait_for_running(sapporo_client, run_id)

        res = sapporo_client.post(f"/runs/{run_id}/cancel")
        res.raise_for_status()

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "CANCELED"

        log = get_run_log(sapporo_client, run_id)
        assert log["run_log"]["exit_code"] == 138

    def test_cancel_already_complete_is_noop(self, sapporo_client: httpx.Client) -> None:
        """Cancelling an already COMPLETE run leaves state unchanged."""
        run_id = submit_workflow(
            sapporo_client,
            wf_type="CWL",
            wf_type_version="v1.2",
            wf_engine="cwltool",
            wf_url="hello.cwl",
            params_file=CWL_DIR / "hello_params.json",
            attachments=[
                CWL_DIR / "hello.cwl",
                CWL_DIR / "input.txt",
            ],
        )

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "COMPLETE"

        res = sapporo_client.post(f"/runs/{run_id}/cancel")
        res.raise_for_status()

        log = get_run_log(sapporo_client, run_id)
        assert log["state"] == "COMPLETE"


class TestCancelStopsStepContainers:
    @pytest.mark.parametrize(
        ("wf_engine", "wf_type", "wf_type_version", "wf_url", "params_file", "attachments", "step_image"),
        STEP_CONTAINER_CASES,
    )
    def test_cancel_stops_the_step_container(
        self,
        sapporo_client: httpx.Client,
        wf_engine: str,
        wf_type: str,
        wf_type_version: str,
        wf_url: str,
        params_file: Path,
        attachments: list[Path],
        step_image: str,
    ) -> None:
        """Cancel while a step container runs -> the engine stops it within the grace period."""
        before = _step_containers(step_image)
        run_id = submit_workflow(
            sapporo_client,
            wf_type=wf_type,
            wf_type_version=wf_type_version,
            wf_engine=wf_engine,
            wf_url=wf_url,
            params_file=params_file,
            attachments=attachments,
        )
        wait_for_running(sapporo_client, run_id)
        assert _wait_until(lambda: bool(_step_containers(step_image) - before), timeout=240), (
            "no step container was started"
        )
        started = _step_containers(step_image) - before

        sapporo_client.post(f"/runs/{run_id}/cancel").raise_for_status()

        assert wait_for_completion(sapporo_client, run_id) == "CANCELED"
        assert _wait_until(lambda: not (_step_containers(step_image) & started), timeout=60), (
            f"step containers still running after cancel: {_step_containers(step_image) & started}"
        )


class TestCancelNonexistent:
    def test_cancel_nonexistent_run_returns_404(self, sapporo_client: httpx.Client) -> None:
        """Cancel with a nonexistent run_id returns 404."""
        res = sapporo_client.post("/runs/00000000-0000-0000-0000-000000000000/cancel")
        assert res.status_code == 404
