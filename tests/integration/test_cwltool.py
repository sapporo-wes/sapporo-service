"""Integration tests for cwltool workflow engine."""

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

CWL_DIR = RESOURCES_DIR / "cwl"


class TestCwltoolHelloWorkflow:
    def test_hello_completes(self, sapporo_client: httpx.Client) -> None:
        """Submit CWL hello workflow -> poll -> assert COMPLETE."""
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

        log = get_run_log(sapporo_client, run_id)
        assert log["run_log"]["exit_code"] == 0
        assert log["outputs"] is not None
        assert len(log["outputs"]) > 0


class TestCwltoolErrorCases:
    def test_nonexistent_workflow_url(self, sapporo_client: httpx.Client) -> None:
        """Submit a run with nonexistent workflow_url -> EXECUTOR_ERROR."""
        run_id = submit_workflow(
            sapporo_client,
            wf_type="CWL",
            wf_type_version="v1.2",
            wf_engine="cwltool",
            wf_url="nonexistent.cwl",
            params_file=CWL_DIR / "hello_params.json",
            attachments=[CWL_DIR / "input.txt"],
        )

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "EXECUTOR_ERROR"

        log = get_run_log(sapporo_client, run_id)
        assert log["run_log"]["exit_code"] != 0
