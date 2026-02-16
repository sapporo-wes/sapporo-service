"""Integration tests for Snakemake workflow engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.integration.conftest import (
    RESOURCES_DIR,
    get_run_log,
    submit_workflow,
    wait_for_completion,
)

if TYPE_CHECKING:
    import httpx

pytestmark = pytest.mark.integration

SMK_DIR = RESOURCES_DIR / "snakemake"


class TestSnakemakeHelloWorkflow:
    def test_hello_completes(self, sapporo_client: httpx.Client) -> None:
        """Submit Snakemake hello workflow -> poll -> assert COMPLETE."""
        run_id = submit_workflow(
            sapporo_client,
            wf_type="SMK",
            wf_type_version="1.0",
            wf_engine="snakemake",
            wf_url="Snakefile",
            params_file=SMK_DIR / "config.json",
            attachments=[
                SMK_DIR / "Snakefile",
                SMK_DIR / "input.txt",
            ],
        )

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "COMPLETE"

        log = get_run_log(sapporo_client, run_id)
        assert log["run_log"]["exit_code"] == 0
        assert log["outputs"] is not None
        assert len(log["outputs"]) > 0


class TestSnakemakeErrorCases:
    def test_nonexistent_workflow_url(self, sapporo_client: httpx.Client) -> None:
        """Submit a run with nonexistent Snakefile -> EXECUTOR_ERROR."""
        run_id = submit_workflow(
            sapporo_client,
            wf_type="SMK",
            wf_type_version="1.0",
            wf_engine="snakemake",
            wf_url="nonexistent_Snakefile",
            params_file=SMK_DIR / "config.json",
            attachments=[SMK_DIR / "input.txt"],
        )

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "EXECUTOR_ERROR"

        log = get_run_log(sapporo_client, run_id)
        assert log["run_log"]["exit_code"] != 0
