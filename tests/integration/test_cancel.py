"""Integration tests for run cancellation lifecycle."""

from __future__ import annotations

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
    import httpx

pytestmark = pytest.mark.integration

CWL_DIR = RESOURCES_DIR / "cwl"


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


class TestCancelNonexistent:
    def test_cancel_nonexistent_run_returns_404(self, sapporo_client: httpx.Client) -> None:
        """Cancel with a nonexistent run_id returns 404."""
        res = sapporo_client.post("/runs/00000000-0000-0000-0000-000000000000/cancel")
        assert res.status_code == 404
