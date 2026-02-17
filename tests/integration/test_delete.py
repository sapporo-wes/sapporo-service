"""Integration tests for run deletion lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.integration.conftest import (
    RESOURCES_DIR,
    get_run_log,
    submit_workflow,
    wait_for_completion,
    wait_for_running,
    wait_for_state,
)

if TYPE_CHECKING:
    import httpx

pytestmark = pytest.mark.integration

CWL_DIR = RESOURCES_DIR / "cwl"


class TestDeleteCompletedRun:
    def test_delete_complete_run(self, sapporo_client: httpx.Client) -> None:
        """Delete a COMPLETE run -> DELETED, run_request becomes None."""
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

        res = sapporo_client.delete(f"/runs/{run_id}")
        res.raise_for_status()

        state = wait_for_state(sapporo_client, run_id, {"DELETED"})
        assert state == "DELETED"

        log = get_run_log(sapporo_client, run_id)
        assert log["request"] is None


class TestDeleteRunningRun:
    def test_delete_running_cancels_first(self, sapporo_client: httpx.Client) -> None:
        """Delete a RUNNING run -> internally cancels then deletes -> DELETED."""
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

        res = sapporo_client.delete(f"/runs/{run_id}")
        res.raise_for_status()

        state = wait_for_state(sapporo_client, run_id, {"DELETED"}, timeout=120)
        assert state == "DELETED"


class TestBulkDelete:
    def test_bulk_delete_multiple_runs(self, sapporo_client: httpx.Client) -> None:
        """Bulk delete two COMPLETE runs -> both become DELETED."""
        run_ids = []
        for _ in range(2):
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
            run_ids.append(run_id)

        for rid in run_ids:
            state = wait_for_completion(sapporo_client, rid)
            assert state == "COMPLETE"

        res = sapporo_client.delete(
            "/runs",
            params=[("run_ids", rid) for rid in run_ids],
        )
        res.raise_for_status()

        for rid in run_ids:
            state = wait_for_state(sapporo_client, rid, {"DELETED"})
            assert state == "DELETED"


class TestDeleteNonexistent:
    def test_delete_nonexistent_run_returns_404(self, sapporo_client: httpx.Client) -> None:
        """Delete with a nonexistent run_id returns 404."""
        res = sapporo_client.delete("/runs/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404
