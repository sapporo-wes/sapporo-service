"""Integration tests for RO-Crate metadata generation and retrieval."""

from __future__ import annotations

import io
import time
import zipfile
from typing import TYPE_CHECKING, Any

import pytest

from tests.integration.conftest import (
    RESOURCES_DIR,
    submit_workflow,
    wait_for_completion,
    wait_for_running,
)

if TYPE_CHECKING:
    from pathlib import Path

    import httpx

pytestmark = pytest.mark.integration

CWL_DIR = RESOURCES_DIR / "cwl"
WDL_DIR = RESOURCES_DIR / "wdl"
NF_DIR = RESOURCES_DIR / "nextflow"
SMK_DIR = RESOURCES_DIR / "snakemake"

_ENGINE_CONFIGS: list[dict[str, Any]] = [
    {
        "id": "cwltool",
        "wf_type": "CWL",
        "wf_type_version": "v1.2",
        "wf_engine": "cwltool",
        "wf_url": "hello.cwl",
        "params_file": CWL_DIR / "hello_params.json",
        "attachments": [CWL_DIR / "hello.cwl", CWL_DIR / "input.txt"],
    },
    {
        "id": "cromwell",
        "wf_type": "WDL",
        "wf_type_version": "1.0",
        "wf_engine": "cromwell",
        "wf_url": "hello.wdl",
        "params_file": WDL_DIR / "hello_params.json",
        "attachments": [WDL_DIR / "hello.wdl", WDL_DIR / "input.txt"],
    },
    {
        "id": "nextflow",
        "wf_type": "NFL",
        "wf_type_version": "DSL2",
        "wf_engine": "nextflow",
        "wf_url": "hello.nf",
        "params_file": NF_DIR / "hello_params.json",
        "attachments": [NF_DIR / "hello.nf", NF_DIR / "input.txt"],
    },
    {
        "id": "snakemake",
        "wf_type": "SMK",
        "wf_type_version": "1.0",
        "wf_engine": "snakemake",
        "wf_url": "Snakefile",
        "params_file": SMK_DIR / "config.json",
        "attachments": [SMK_DIR / "Snakefile", SMK_DIR / "input.txt"],
    },
    {
        "id": "toil",
        "wf_type": "CWL",
        "wf_type_version": "v1.2",
        "wf_engine": "toil",
        "wf_url": "hello.cwl",
        "params_file": CWL_DIR / "hello_params.json",
        "attachments": [CWL_DIR / "hello.cwl", CWL_DIR / "input.txt"],
    },
    {
        "id": "ep3",
        "wf_type": "CWL",
        "wf_type_version": "v1.2",
        "wf_engine": "ep3",
        "wf_url": "hello.cwl",
        "params_file": CWL_DIR / "hello_params.json",
        "attachments": [CWL_DIR / "hello.cwl", CWL_DIR / "input.txt"],
    },
    {
        "id": "streamflow",
        "wf_type": "CWL",
        "wf_type_version": "v1.2",
        "wf_engine": "streamflow",
        "wf_url": "hello.cwl",
        "params_file": CWL_DIR / "hello_params.json",
        "attachments": [CWL_DIR / "hello.cwl", CWL_DIR / "input.txt"],
    },
]


def _submit_hello(client: httpx.Client) -> str:
    return submit_workflow(
        client,
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


def _get_ro_crate_json(client: httpx.Client, run_id: str, *, timeout: int = 30) -> dict[str, Any]:
    """Get RO-Crate JSON, retrying until @graph is present.

    run.sh sets COMPLETE *before* calling generate_ro_crate, so a short
    polling window is needed. Tolerates 404 responses (file not yet written).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = client.get(f"/runs/{run_id}/ro-crate")
        if res.status_code == 404:
            time.sleep(2)
            continue
        res.raise_for_status()
        result: dict[str, Any] = res.json()
        if result and "@graph" in result:
            return result
        time.sleep(2)
    msg = f"RO-Crate for run {run_id} not ready within {timeout}s"
    raise TimeoutError(msg)


class TestRoCrateForCompleteRun:
    def test_ro_crate_json_ld_structure(self, sapporo_client: httpx.Client) -> None:
        """COMPLETE run RO-Crate has valid JSON-LD with expected entities."""
        run_id = _submit_hello(sapporo_client)
        state = wait_for_completion(sapporo_client, run_id)
        assert state == "COMPLETE"

        ro_crate = _get_ro_crate_json(sapporo_client, run_id)

        # Top-level JSON-LD structure
        assert "@context" in ro_crate
        assert "@graph" in ro_crate

        graph = ro_crate["@graph"]
        entities_by_type: dict[str, list[dict[str, Any]]] = {}
        for entity in graph:
            entity_type = entity.get("@type", "")
            if isinstance(entity_type, list):
                for t in entity_type:
                    entities_by_type.setdefault(t, []).append(entity)
            else:
                entities_by_type.setdefault(entity_type, []).append(entity)

        # Root dataset conformsTo WRROC profiles
        root_datasets = [e for e in graph if e.get("@id") == "./"]
        assert len(root_datasets) == 1
        root = root_datasets[0]
        conforms_to = root.get("conformsTo", [])
        conforms_ids = {c["@id"] if isinstance(c, dict) else c for c in conforms_to}
        assert any("process" in cid and "0.5" in cid for cid in conforms_ids)
        assert any("workflow" in cid and "0.5" in cid for cid in conforms_ids)

        # CreateAction with CompletedActionStatus
        assert "CreateAction" in entities_by_type
        action = entities_by_type["CreateAction"][0]
        action_status = action["actionStatus"]
        if isinstance(action_status, dict):
            assert action_status["@id"] == "http://schema.org/CompletedActionStatus"
        else:
            assert action_status == "http://schema.org/CompletedActionStatus"
        assert action.get("exitCode") == 0

        # ComputationalWorkflow entity
        assert "ComputationalWorkflow" in entities_by_type

    def test_ro_crate_zip_download(self, sapporo_client: httpx.Client) -> None:
        """download=true returns a valid ZIP containing ro-crate-metadata.json."""
        run_id = _submit_hello(sapporo_client)
        state = wait_for_completion(sapporo_client, run_id)
        assert state == "COMPLETE"

        # Wait for RO-Crate generation (runs after state -> COMPLETE)
        _get_ro_crate_json(sapporo_client, run_id)

        res = sapporo_client.get(f"/runs/{run_id}/ro-crate", params={"download": "true"})
        res.raise_for_status()
        assert "application/zip" in res.headers.get("content-type", "")

        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            names = zf.namelist()
            assert any("ro-crate-metadata.json" in n for n in names)

    @pytest.mark.slow
    def test_roc_validator_required_pass_complete(self, sapporo_client: httpx.Client, tmp_path: Path) -> None:
        """REQUIRED checks pass for a COMPLETE run's RO-Crate."""
        from rocrate_validator.models import Severity, ValidationSettings
        from rocrate_validator.services import validate

        run_id = _submit_hello(sapporo_client)
        state = wait_for_completion(sapporo_client, run_id)
        assert state == "COMPLETE"

        # Wait for RO-Crate generation
        _get_ro_crate_json(sapporo_client, run_id)

        # Download the ZIP and extract
        res = sapporo_client.get(f"/runs/{run_id}/ro-crate", params={"download": "true"})
        res.raise_for_status()
        crate_dir = tmp_path / "crate"
        crate_dir.mkdir()
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            zf.extractall(crate_dir)

        # The ZIP wraps contents in a subdirectory; find the one with ro-crate-metadata.json
        metadata_files = list(crate_dir.rglob("ro-crate-metadata.json"))
        assert len(metadata_files) >= 1
        actual_crate_dir = metadata_files[0].parent

        settings_obj = ValidationSettings(
            rocrate_uri=str(actual_crate_dir),
            profile_identifier="workflow-run-crate",
            requirement_severity=Severity.REQUIRED,
        )
        result = validate(settings_obj)

        for issue in result.get_issues():
            print(f"  [{issue.severity}] {issue.message}")

        assert result.passed(), f"REQUIRED violations: {[i.message for i in result.get_issues()]}"


class TestRoCrateForFailedRun:
    def test_ro_crate_has_failed_action_status(self, sapporo_client: httpx.Client) -> None:
        """EXECUTOR_ERROR run RO-Crate has FailedActionStatus and error field."""
        run_id = submit_workflow(
            sapporo_client,
            wf_type="CWL",
            wf_type_version="v1.2",
            wf_engine="cwltool",
            wf_url="fail.cwl",
            params_file=CWL_DIR / "sleep_params.json",
            attachments=[CWL_DIR / "fail.cwl"],
        )

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "EXECUTOR_ERROR"

        ro_crate = _get_ro_crate_json(sapporo_client, run_id)
        graph = ro_crate["@graph"]
        actions = [
            e
            for e in graph
            if "CreateAction" in (e.get("@type") if isinstance(e.get("@type"), list) else [e.get("@type", "")])
        ]
        assert len(actions) >= 1
        action = actions[0]
        action_status = action["actionStatus"]
        if isinstance(action_status, dict):
            assert action_status["@id"] == "http://schema.org/FailedActionStatus"
        else:
            assert action_status == "http://schema.org/FailedActionStatus"
        assert action.get("exitCode") != 0
        assert action.get("error") is not None

    @pytest.mark.slow
    def test_roc_validator_required_pass_failed(self, sapporo_client: httpx.Client, tmp_path: Path) -> None:
        """REQUIRED checks pass for an EXECUTOR_ERROR run's RO-Crate."""
        from rocrate_validator.models import Severity, ValidationSettings
        from rocrate_validator.services import validate

        run_id = submit_workflow(
            sapporo_client,
            wf_type="CWL",
            wf_type_version="v1.2",
            wf_engine="cwltool",
            wf_url="fail.cwl",
            params_file=CWL_DIR / "sleep_params.json",
            attachments=[CWL_DIR / "fail.cwl"],
        )

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "EXECUTOR_ERROR"

        # Wait for RO-Crate generation
        _get_ro_crate_json(sapporo_client, run_id)

        res = sapporo_client.get(f"/runs/{run_id}/ro-crate", params={"download": "true"})
        res.raise_for_status()
        crate_dir = tmp_path / "crate"
        crate_dir.mkdir()
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            zf.extractall(crate_dir)

        metadata_files = list(crate_dir.rglob("ro-crate-metadata.json"))
        assert len(metadata_files) >= 1
        actual_crate_dir = metadata_files[0].parent

        settings_obj = ValidationSettings(
            rocrate_uri=str(actual_crate_dir),
            profile_identifier="workflow-run-crate",
            requirement_severity=Severity.REQUIRED,
        )
        result = validate(settings_obj)

        for issue in result.get_issues():
            print(f"  [{issue.severity}] {issue.message}")

        assert result.passed(), f"REQUIRED violations: {[i.message for i in result.get_issues()]}"


class TestRoCrateForCanceledRun:
    def test_no_ro_crate_for_canceled(self, sapporo_client: httpx.Client) -> None:
        """CANCELED run has no RO-Crate (returns 404)."""
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
        sapporo_client.post(f"/runs/{run_id}/cancel")

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "CANCELED"

        res = sapporo_client.get(f"/runs/{run_id}/ro-crate")
        assert res.status_code == 404


class TestRoCrateEntities:
    def test_formal_parameters_present(self, sapporo_client: httpx.Client) -> None:
        """COMPLETE run RO-Crate contains FormalParameter entities."""
        run_id = _submit_hello(sapporo_client)
        state = wait_for_completion(sapporo_client, run_id)
        assert state == "COMPLETE"

        ro_crate = _get_ro_crate_json(sapporo_client, run_id)
        graph = ro_crate["@graph"]
        fp_entities = [e for e in graph if e.get("@type") == "FormalParameter"]
        assert len(fp_entities) > 0

    def test_container_image_present(self, sapporo_client: httpx.Client) -> None:
        """COMPLETE run CreateAction has containerImage set."""
        run_id = _submit_hello(sapporo_client)
        state = wait_for_completion(sapporo_client, run_id)
        assert state == "COMPLETE"

        ro_crate = _get_ro_crate_json(sapporo_client, run_id)
        graph = ro_crate["@graph"]
        actions = [
            e
            for e in graph
            if "CreateAction" in (e.get("@type") if isinstance(e.get("@type"), list) else [e.get("@type", "")])
        ]
        assert len(actions) >= 1
        action = actions[0]
        assert action.get("containerImage") is not None


def _submit_engine(client: httpx.Client, engine: dict[str, Any]) -> str:
    return submit_workflow(
        client,
        wf_type=engine["wf_type"],
        wf_type_version=engine["wf_type_version"],
        wf_engine=engine["wf_engine"],
        wf_url=engine["wf_url"],
        params_file=engine["params_file"],
        attachments=engine["attachments"],
    )


def _get_ro_crate_or_error(
    client: httpx.Client,
    run_id: str,
    *,
    timeout: int = 60,
) -> dict[str, Any]:
    """Get RO-Crate JSON, retrying until @graph or @error is present.

    Tolerates 404 responses (file not yet written by run.sh).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = client.get(f"/runs/{run_id}/ro-crate")
        if res.status_code == 404:
            time.sleep(2)
            continue
        res.raise_for_status()
        result: dict[str, Any] = res.json()
        if result and ("@graph" in result or "@error" in result):
            return result
        time.sleep(2)
    msg = f"RO-Crate for run {run_id} not ready within {timeout}s"
    raise TimeoutError(msg)


class TestRoCrateMultiEngine:
    @pytest.mark.slow
    @pytest.mark.parametrize("engine", _ENGINE_CONFIGS, ids=lambda e: e["id"])
    def test_roc_validator_required_pass(
        self,
        sapporo_client: httpx.Client,
        tmp_path: Path,
        engine: dict[str, Any],
    ) -> None:
        """REQUIRED checks pass for each engine's hello workflow RO-Crate."""
        from rocrate_validator.models import Severity, ValidationSettings
        from rocrate_validator.services import validate

        run_id = _submit_engine(sapporo_client, engine)
        state = wait_for_completion(sapporo_client, run_id, timeout=600)
        assert state == "COMPLETE"

        _get_ro_crate_json(sapporo_client, run_id, timeout=60)

        res = sapporo_client.get(f"/runs/{run_id}/ro-crate", params={"download": "true"})
        res.raise_for_status()
        crate_dir = tmp_path / "crate"
        crate_dir.mkdir()
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            zf.extractall(crate_dir)

        metadata_files = list(crate_dir.rglob("ro-crate-metadata.json"))
        assert len(metadata_files) >= 1
        actual_crate_dir = metadata_files[0].parent

        settings_obj = ValidationSettings(
            rocrate_uri=str(actual_crate_dir),
            profile_identifier="workflow-run-crate",
            requirement_severity=Severity.REQUIRED,
        )
        result = validate(settings_obj)

        for issue in result.get_issues():
            print(f"  [{issue.severity}] {issue.message}")

        assert result.passed(), f"REQUIRED violations for {engine['id']}: {[i.message for i in result.get_issues()]}"


class TestRoCrateGenerationFailure:
    def test_nonexistent_wf_url_produces_failed_ro_crate(self, sapporo_client: httpx.Client) -> None:
        """EXECUTOR_ERROR with missing wf file -> RO-Crate records FailedActionStatus."""
        run_id = submit_workflow(
            sapporo_client,
            wf_type="CWL",
            wf_type_version="v1.2",
            wf_engine="cwltool",
            wf_url="nonexistent.cwl",
            params_file=CWL_DIR / "sleep_params.json",
            attachments=[],
        )

        state = wait_for_completion(sapporo_client, run_id)
        assert state == "EXECUTOR_ERROR"

        ro_crate = _get_ro_crate_or_error(sapporo_client, run_id, timeout=60)
        assert "@graph" in ro_crate

        # Find the CreateAction entity in the graph
        actions = [e for e in ro_crate["@graph"] if "CreateAction" in (e.get("@type") if isinstance(e.get("@type"), list) else [e.get("@type", "")])]
        assert len(actions) == 1
        action = actions[0]
        assert action["actionStatus"] == "http://schema.org/FailedActionStatus"
        assert action["exitCode"] == 1
        assert "error" in action


class TestRoCrateTrimmingAndQc:
    """RO-Crate validation for Trimmomatic + FastQC CWL workflow."""

    @pytest.mark.slow
    def test_roc_validator_required_pass(self, sapporo_client: httpx.Client, tmp_path: Path) -> None:
        """REQUIRED checks pass for trimming_and_qc workflow RO-Crate."""
        from rocrate_validator.models import Severity, ValidationSettings
        from rocrate_validator.services import validate

        run_id = submit_workflow(
            sapporo_client,
            wf_type="CWL",
            wf_type_version="v1.2",
            wf_engine="cwltool",
            wf_url="trimming_and_qc.cwl",
            params_file=CWL_DIR / "trimming_and_qc_params.json",
            attachments=[
                CWL_DIR / "trimming_and_qc.cwl",
                CWL_DIR / "fastqc.cwl",
                CWL_DIR / "trimmomatic_pe.cwl",
                CWL_DIR / "ERR034597_1.small.fq.gz",
                CWL_DIR / "ERR034597_2.small.fq.gz",
            ],
        )

        state = wait_for_completion(sapporo_client, run_id, timeout=600)
        assert state == "COMPLETE"

        ro_crate = _get_ro_crate_json(sapporo_client, run_id, timeout=120)

        # Verify multi-output workflow produces richer RO-Crate
        graph = ro_crate["@graph"]
        actions = [
            e
            for e in graph
            if "CreateAction" in (e.get("@type") if isinstance(e.get("@type"), list) else [e.get("@type", "")])
        ]
        assert len(actions) >= 1
        action = actions[0]
        assert action.get("exitCode") == 0

        results = action.get("result", [])
        if not isinstance(results, list):
            results = [results]
        assert len(results) >= 6

        # Download ZIP and run roc-validator
        res = sapporo_client.get(f"/runs/{run_id}/ro-crate", params={"download": "true"})
        res.raise_for_status()
        crate_dir = tmp_path / "crate"
        crate_dir.mkdir()
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            zf.extractall(crate_dir)

        metadata_files = list(crate_dir.rglob("ro-crate-metadata.json"))
        assert len(metadata_files) >= 1
        actual_crate_dir = metadata_files[0].parent

        settings_obj = ValidationSettings(
            rocrate_uri=str(actual_crate_dir),
            profile_identifier="workflow-run-crate",
            requirement_severity=Severity.REQUIRED,
        )
        result = validate(settings_obj)

        for issue in result.get_issues():
            print(f"  [{issue.severity}] {issue.message}")

        assert result.passed(), f"REQUIRED violations: {[i.message for i in result.get_issues()]}"
