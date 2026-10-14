"""Integration tests for Cromwell workflow engine (WDL)."""

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

WDL_DIR = RESOURCES_DIR / "wdl"


class TestCromwellHelloWorkflow:
    def test_hello_completes(self, sapporo_client: httpx.Client) -> None:
        """Submit WDL hello workflow via Cromwell -> poll -> assert COMPLETE."""
        run_id = submit_workflow(
            sapporo_client,
            wf_type="WDL",
            wf_type_version="1.0",
            wf_engine="cromwell",
            wf_url="hello.wdl",
            params_file=WDL_DIR / "hello_params.json",
            attachments=[
                WDL_DIR / "hello.wdl",
                WDL_DIR / "input.txt",
            ],
        )

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "COMPLETE"

        log = get_run_log(sapporo_client, run_id)
        assert log["run_log"]["exit_code"] == 0
        assert log["outputs"] is not None
        assert len(log["outputs"]) > 0


class TestCromwellErrorCases:
    def test_nonexistent_workflow_url(self, sapporo_client: httpx.Client) -> None:
        """Submit a run with nonexistent workflow_url -> EXECUTOR_ERROR."""
        run_id = submit_workflow(
            sapporo_client,
            wf_type="WDL",
            wf_type_version="1.0",
            wf_engine="cromwell",
            wf_url="nonexistent.wdl",
            params_file=WDL_DIR / "hello_params.json",
            attachments=[WDL_DIR / "input.txt"],
        )

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "EXECUTOR_ERROR"

        log = get_run_log(sapporo_client, run_id)
        assert log["run_log"]["exit_code"] != 0


class TestCromwellArrayOutputs:
    def test_scatter_outputs_are_copied(self, sapporo_client: httpx.Client) -> None:
        """Every member of an Array[File] output ends up in outputs/."""
        run_id = submit_workflow(
            sapporo_client,
            wf_type="WDL",
            wf_type_version="1.0",
            wf_engine="cromwell",
            wf_url="scatter.wdl",
            params_file=WDL_DIR / "scatter_params.json",
            attachments=[WDL_DIR / "scatter.wdl"],
        )

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "COMPLETE"

        log = get_run_log(sapporo_client, run_id)
        names = {output["file_name"] for output in log["outputs"]}
        assert {"out_1.txt", "out_2.txt", "out_3.txt"} <= names
