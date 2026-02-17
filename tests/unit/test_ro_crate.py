"""Tests for sapporo.ro_crate module (WRROC 0.5 / RO-Crate 1.1)."""

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from rocrate.model.metadata import WORKFLOW_PROFILE

from sapporo.ro_crate import (
    BIOSCHEMAS_COMPUTATIONAL_WORKFLOW,
    BIOSCHEMAS_FORMAL_PARAMETER,
    PROCESS_RUN_PROFILE,
    SAPPORO_CONTEXT,
    WFRUN_CONTEXT,
    WORKFLOW_RUN_PROFILE,
    _ensure_tz,
    add_create_action,
    add_file_stats,
    add_multiqc_stats,
    add_samtools_stats,
    add_vcftools_stats,
    add_workflow_entity,
    compute_sha256,
    count_lines,
    create_base_crate,
    extract_docker_image,
    find_or_generate_software_ins,
    generate_ro_crate,
    generate_ro_crate_metadata,
    infer_parameter_type,
    inspect_edam_format,
    populate_file_metadata,
    resolve_workflow_language,
)
from tests.unit.conftest import create_run_dir, make_run_request_form

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

RUN_ID = "ab12cd34-ef56-7890-abcd-ef1234567890"


# === create_base_crate ===


class TestCreateBaseCrate:
    def test_context_contains_three_urls(self) -> None:
        crate = create_base_crate()
        jsonld = crate.metadata.generate()
        context = jsonld["@context"]
        assert isinstance(context, list)
        assert WFRUN_CONTEXT in context
        assert SAPPORO_CONTEXT in context

    def test_root_conforms_to_three_profiles(self) -> None:
        crate = create_base_crate()
        root = None
        for entity in crate.get_entities():
            if entity.id == "./":
                root = entity
                break
        assert root is not None
        conforms = root.get("conformsTo", [])
        if not isinstance(conforms, list):
            conforms = [conforms]
        conforms_ids = set()
        for c in conforms:
            if isinstance(c, dict):
                conforms_ids.add(c["@id"])
            elif hasattr(c, "id"):
                conforms_ids.add(c.id)
            else:
                conforms_ids.add(str(c))
        assert PROCESS_RUN_PROFILE in conforms_ids
        assert WORKFLOW_RUN_PROFILE in conforms_ids
        assert WORKFLOW_PROFILE in conforms_ids

    def test_metadata_conforms_to_ro_crate(self) -> None:
        crate = create_base_crate()
        metadata = None
        for entity in crate.get_entities():
            if entity.id == "ro-crate-metadata.json":
                metadata = entity
                break
        assert metadata is not None
        conforms = metadata.get("conformsTo")
        assert conforms is not None


# === infer_parameter_type ===


class TestInferParameterType:
    def test_bool_returns_boolean(self) -> None:
        assert infer_parameter_type(True) == "Boolean"
        assert infer_parameter_type(False) == "Boolean"

    def test_int_returns_integer(self) -> None:
        assert infer_parameter_type(42) == "Integer"
        assert infer_parameter_type(0) == "Integer"
        assert infer_parameter_type(-1) == "Integer"

    def test_float_returns_float(self) -> None:
        assert infer_parameter_type(3.14) == "Float"
        assert infer_parameter_type(0.0) == "Float"

    def test_cwl_file_object_returns_file(self) -> None:
        assert infer_parameter_type({"class": "File", "path": "/data/input.fastq"}) == "File"

    def test_string_returns_text(self) -> None:
        assert infer_parameter_type("hello") == "Text"

    def test_list_returns_text(self) -> None:
        assert infer_parameter_type([1, 2, 3]) == "Text"

    def test_none_returns_text(self) -> None:
        assert infer_parameter_type(None) == "Text"

    def test_dict_without_class_returns_text(self) -> None:
        assert infer_parameter_type({"key": "value"}) == "Text"

    def test_bool_before_int(self) -> None:
        """Bool is a subclass of int in Python, so bool must be checked first."""
        assert infer_parameter_type(True) == "Boolean"
        assert infer_parameter_type(False) == "Boolean"

    @given(st.booleans())
    def test_pbt_booleans_always_boolean(self, value: bool) -> None:
        assert infer_parameter_type(value) == "Boolean"

    @given(st.integers())
    def test_pbt_integers_always_integer(self, value: int) -> None:
        assert infer_parameter_type(value) == "Integer"

    @given(st.floats(allow_nan=False, allow_infinity=False))
    def test_pbt_floats_always_float(self, value: float) -> None:
        assert infer_parameter_type(value) == "Float"

    @given(st.text())
    def test_pbt_strings_always_text(self, value: str) -> None:
        assert infer_parameter_type(value) == "Text"


# === compute_sha256 ===


class TestComputeSha256:
    def test_known_hash(self, tmp_path: Path) -> None:
        content = b"hello world\n"
        f = tmp_path.joinpath("test.txt")
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert compute_sha256(f) == expected

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path.joinpath("empty.txt")
        f.write_bytes(b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert compute_sha256(f) == expected

    @given(st.binary(min_size=0, max_size=1024))
    @settings(max_examples=20)
    def test_pbt_deterministic(self, data: bytes) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            f = Path(tmp.name)
            assert compute_sha256(f) == compute_sha256(f)

    @given(st.binary(min_size=0, max_size=1024))
    @settings(max_examples=20)
    def test_pbt_matches_hashlib(self, data: bytes) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            f = Path(tmp.name)
            expected = hashlib.sha256(data).hexdigest()
            assert compute_sha256(f) == expected


# === extract_docker_image ===


class TestExtractDockerImage:
    def test_cwltool(self) -> None:
        cmd = "docker run --rm -v /var/run/docker.sock:/var/run/docker.sock quay.io/commonwl/cwltool:3.1.20260108082145 --outdir /outputs wf.cwl params.json"
        assert extract_docker_image(cmd) == ("quay.io/commonwl/cwltool", "3.1.20260108082145")

    def test_nextflow(self) -> None:
        cmd = "docker run --rm -v /run:/run nextflow/nextflow:25.10.4 nextflow run wf.nf"
        assert extract_docker_image(cmd) == ("nextflow/nextflow", "25.10.4")

    def test_cromwell(self) -> None:
        cmd = "docker run --rm ghcr.io/sapporo-wes/cromwell-with-docker:92 run wf.wdl"
        assert extract_docker_image(cmd) == ("ghcr.io/sapporo-wes/cromwell-with-docker", "92")

    def test_snakemake(self) -> None:
        cmd = "docker run --rm snakemake/snakemake:v9.16.3 bash -c 'snakemake ...'"
        assert extract_docker_image(cmd) == ("snakemake/snakemake", "v9.16.3")

    def test_ep3(self) -> None:
        cmd = "docker run --rm ghcr.io/tom-tan/ep3:v1.7.0 ep3-runner --verbose"
        assert extract_docker_image(cmd) == ("ghcr.io/tom-tan/ep3", "v1.7.0")

    def test_streamflow(self) -> None:
        cmd = "docker run --mount type=bind,source=/run,target=/streamflow/project alphaunito/streamflow:0.2.0.dev14 run /streamflow/project/wf.cwl"
        assert extract_docker_image(cmd) == ("alphaunito/streamflow", "0.2.0.dev14")

    def test_no_docker(self) -> None:
        assert extract_docker_image("python3 script.py") is None

    def test_empty_string(self) -> None:
        assert extract_docker_image("") is None

    def test_toil(self) -> None:
        cmd = "docker run --rm -v /var/run/docker.sock:/var/run/docker.sock quay.io/ucsc_cgl/toil:9.1.1 toil-cwl-runner wf.cwl"
        assert extract_docker_image(cmd) == ("quay.io/ucsc_cgl/toil", "9.1.1")


# === resolve_workflow_language ===


class TestResolveWorkflowLanguage:
    def test_cwl(self) -> None:
        crate = create_base_crate()
        req = make_run_request_form(workflow_type="CWL", workflow_type_version="v1.0")
        lang = resolve_workflow_language(crate, req)
        name = lang.get("name", "") or ""
        alt = lang.get("alternateName", "") or ""
        assert "CWL" in name or "CWL" in alt or "cwl" in lang.id.lower() or "Common Workflow Language" in name

    def test_wdl(self) -> None:
        crate = create_base_crate()
        req = make_run_request_form(workflow_type="WDL", workflow_type_version="1.0")
        lang = resolve_workflow_language(crate, req)
        assert lang.get("name") == "Workflow Description Language"

    def test_nfl(self) -> None:
        crate = create_base_crate()
        req = make_run_request_form(workflow_type="NFL", workflow_type_version="21.04.0")
        lang = resolve_workflow_language(crate, req)
        assert lang is not None

    def test_smk(self) -> None:
        crate = create_base_crate()
        req = make_run_request_form(workflow_type="SMK", workflow_type_version="7.0")
        lang = resolve_workflow_language(crate, req)
        assert lang is not None

    def test_unknown_language(self) -> None:
        crate = create_base_crate()
        req = make_run_request_form(workflow_type="UNKNOWN", workflow_type_version="1.0")
        lang = resolve_workflow_language(crate, req)
        assert lang.get("name") == "UNKNOWN"


# === add_workflow_entity ===


class TestAddWorkflowEntity:
    def test_remote_url(self, tmp_path: Path) -> None:
        rd = create_run_dir(tmp_path, RUN_ID, exit_code="0", end_time="2024-01-01T00:00:00")
        crate = create_base_crate()
        req = make_run_request_form(workflow_url="https://example.com/wf.cwl")
        wf = add_workflow_entity(crate, rd, req)
        assert wf["@id"] == "https://example.com/wf.cwl"
        types = wf.get("@type", [])
        assert "ComputationalWorkflow" in types

    def test_local_file(self, tmp_path: Path) -> None:
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            run_request_dict={
                "workflow_params": "{}",
                "workflow_type": "CWL",
                "workflow_type_version": "v1.0",
                "tags": {},
                "workflow_engine": "cwltool",
                "workflow_engine_version": None,
                "workflow_engine_parameters": None,
                "workflow_url": "wf.cwl",
            },
            exit_code="0",
            end_time="2024-01-01T00:00:00",
        )
        rd.joinpath("exe", "wf.cwl").write_text("class: Workflow", encoding="utf-8")
        crate = create_base_crate()
        req = make_run_request_form(workflow_url="wf.cwl")
        wf = add_workflow_entity(crate, rd, req)
        assert "exe/wf.cwl" in str(wf["@id"])

    def test_programming_language_set(self, tmp_path: Path) -> None:
        rd = create_run_dir(tmp_path, RUN_ID, exit_code="0", end_time="2024-01-01T00:00:00")
        crate = create_base_crate()
        req = make_run_request_form()
        wf = add_workflow_entity(crate, rd, req)
        assert wf.get("programmingLanguage") is not None


# === add_create_action ===


class TestAddCreateAction:
    def _make_crate_with_wf(self, tmp_path: Path, **kwargs: Any) -> tuple[Any, Any, Path]:
        rd = create_run_dir(tmp_path, RUN_ID, **kwargs)
        crate = create_base_crate()
        req = make_run_request_form()
        wf = add_workflow_entity(crate, rd, req)

        return crate, wf, rd

    def test_completed_action_status(self, tmp_path: Path) -> None:
        crate, wf, rd = self._make_crate_with_wf(
            tmp_path,
            exit_code="0",
            end_time="2024-01-01T00:00:00",
            wf_params="{}",
        )
        action = add_create_action(crate, wf, rd, make_run_request_form(), RUN_ID)
        assert action["actionStatus"] == "http://schema.org/CompletedActionStatus"
        assert action["exitCode"] == 0

    def test_failed_action_status(self, tmp_path: Path) -> None:
        crate, wf, rd = self._make_crate_with_wf(
            tmp_path,
            exit_code="1",
            end_time="2024-01-01T00:00:00",
            stderr_content="Error: something went wrong\n",
            wf_params="{}",
        )
        action = add_create_action(crate, wf, rd, make_run_request_form(), RUN_ID)
        assert action["actionStatus"] == "http://schema.org/FailedActionStatus"
        assert action["exitCode"] == 1
        assert action.get("error") is not None

    def test_timestamps_present(self, tmp_path: Path) -> None:
        crate, wf, rd = self._make_crate_with_wf(
            tmp_path,
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:10:00",
            exit_code="0",
            wf_params="{}",
        )
        action = add_create_action(crate, wf, rd, make_run_request_form(), RUN_ID)
        assert action["startTime"] == "2024-01-01T00:00:00+00:00"
        assert action["endTime"] == "2024-01-01T00:10:00+00:00"

    def test_agent_from_username(self, tmp_path: Path) -> None:
        crate, wf, rd = self._make_crate_with_wf(
            tmp_path,
            exit_code="0",
            end_time="2024-01-01T00:00:00",
            username="testuser",
            wf_params="{}",
        )
        action = add_create_action(crate, wf, rd, make_run_request_form(), RUN_ID)
        agent_ref = action.get("agent")
        assert agent_ref is not None

    def test_container_image_from_cmd(self, tmp_path: Path) -> None:
        crate, wf, rd = self._make_crate_with_wf(
            tmp_path,
            exit_code="0",
            end_time="2024-01-01T00:00:00",
            cmd="docker run --rm quay.io/commonwl/cwltool:3.1 --outdir /out wf.cwl",
            wf_params="{}",
        )
        action = add_create_action(crate, wf, rd, make_run_request_form(), RUN_ID)
        container_ref = action.get("containerImage")
        assert container_ref is not None

    def test_agent_entity_properties(self, tmp_path: Path) -> None:
        crate, wf, rd = self._make_crate_with_wf(
            tmp_path,
            exit_code="0",
            end_time="2024-01-01T00:00:00",
            username="alice",
            wf_params="{}",
        )
        add_create_action(crate, wf, rd, make_run_request_form(), RUN_ID)

        agent_entity = None
        for entity in crate.get_entities():
            if entity.id == "#agent-alice":
                agent_entity = entity
                break
        assert agent_entity is not None
        assert agent_entity["@type"] == "Person"
        assert agent_entity["name"] == "alice"

    def test_description_is_summary(self, tmp_path: Path) -> None:
        cmd_text = "docker run --rm quay.io/commonwl/cwltool:3.1 --outdir /out wf.cwl"
        crate, wf, rd = self._make_crate_with_wf(
            tmp_path,
            exit_code="0",
            end_time="2024-01-01T00:00:00",
            cmd=cmd_text,
            wf_params="{}",
        )
        action = add_create_action(crate, wf, rd, make_run_request_form(), RUN_ID)
        assert action["description"] == "Executed wf.cwl using cwltool"


# === add_input_parameters ===


class TestAddInputParameters:
    def test_json_dict_params(self, tmp_path: Path) -> None:
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:00:00",
            wf_params='{"message": "hello", "count": 5, "flag": true}',
        )
        crate = create_base_crate()
        req = make_run_request_form()
        wf = add_workflow_entity(crate, rd, req)
        action = add_create_action(crate, wf, rd, req, RUN_ID)

        inputs = wf.get("input", [])
        if not isinstance(inputs, list):
            inputs = [inputs]
        assert len(inputs) >= 3

        objects = action.get("object", [])
        if not isinstance(objects, list):
            objects = [objects]
        pv_ids = set()
        for o in objects:
            if isinstance(o, dict):
                pv_ids.add(o["@id"])
            elif hasattr(o, "id"):
                pv_ids.add(o.id)
            else:
                pv_ids.add(str(o))
        assert "#pv-message" in pv_ids

    def test_non_dict_params_fallback(self, tmp_path: Path) -> None:
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:00:00",
            wf_params="not valid json",
        )
        crate = create_base_crate()
        req = make_run_request_form()
        wf = add_workflow_entity(crate, rd, req)
        add_create_action(crate, wf, rd, req, RUN_ID)

        inputs = wf.get("input", [])
        if not isinstance(inputs, list):
            inputs = [inputs]
        assert len(inputs) >= 1

    def test_bidirectional_links(self, tmp_path: Path) -> None:
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:00:00",
            wf_params='{"x": 1}',
        )
        crate = create_base_crate()
        req = make_run_request_form()
        wf = add_workflow_entity(crate, rd, req)
        add_create_action(crate, wf, rd, req, RUN_ID)

        fp_entity = None
        pv_entity = None
        for entity in crate.get_entities():
            if entity.id == "#param-input-x":
                fp_entity = entity
            if entity.id == "#pv-x":
                pv_entity = entity
        assert fp_entity is not None
        assert pv_entity is not None
        assert pv_entity.get("exampleOfWork") is not None
        assert fp_entity.get("workExample") is not None


# === add_output_parameters ===


class TestAddOutputParameters:
    def test_output_files_generate_formal_parameters(self, tmp_path: Path) -> None:
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:00:00",
            wf_params="{}",
            output_files={"result.txt": "output data"},
            outputs_json=[{"file_name": "result.txt", "file_url": "http://localhost/result.txt"}],
        )
        crate = create_base_crate()
        req = make_run_request_form()
        wf = add_workflow_entity(crate, rd, req)
        add_create_action(crate, wf, rd, req, RUN_ID)

        outputs = wf.get("output", [])
        if not isinstance(outputs, list):
            outputs = [outputs]
        assert len(outputs) >= 1


# === populate_file_metadata ===


class TestPopulateFileMetadata:
    def test_sha256_present(self, tmp_path: Path) -> None:
        f = tmp_path.joinpath("test.txt")
        f.write_text("hello", encoding="utf-8")
        crate = create_base_crate()
        from rocrate.model.file import File

        file_ins = File(crate, f, f.name)
        populate_file_metadata(file_ins, f)
        assert file_ins.get("sha256") is not None
        assert "sha512" not in dict(file_ins.properties())

    def test_content_size(self, tmp_path: Path) -> None:
        f = tmp_path.joinpath("test.txt")
        f.write_text("hello", encoding="utf-8")
        crate = create_base_crate()
        from rocrate.model.file import File

        file_ins = File(crate, f, f.name)
        populate_file_metadata(file_ins, f)
        assert file_ins["contentSize"] == f.stat().st_size

    def test_line_count(self, tmp_path: Path) -> None:
        f = tmp_path.joinpath("test.txt")
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")
        crate = create_base_crate()
        from rocrate.model.file import File

        file_ins = File(crate, f, f.name)
        populate_file_metadata(file_ins, f)
        assert file_ins["lineCount"] == 3

    def test_text_embedded_under_10kb(self, tmp_path: Path) -> None:
        f = tmp_path.joinpath("small.txt")
        content = "small content"
        f.write_text(content, encoding="utf-8")
        crate = create_base_crate()
        from rocrate.model.file import File

        file_ins = File(crate, f, f.name)
        populate_file_metadata(file_ins, f)
        assert file_ins.get("text") == content

    def test_text_not_embedded_over_10kb(self, tmp_path: Path) -> None:
        f = tmp_path.joinpath("large.txt")
        content = "x" * (11 * 1024)
        f.write_text(content, encoding="utf-8")
        crate = create_base_crate()
        from rocrate.model.file import File

        file_ins = File(crate, f, f.name)
        populate_file_metadata(file_ins, f)
        assert file_ins.get("text") is None

    def test_edam_format_for_bam(self, tmp_path: Path) -> None:
        f = tmp_path.joinpath("test.bam")
        f.write_bytes(b"\x00" * 100)
        crate = create_base_crate()
        from rocrate.model.file import File

        file_ins = File(crate, f, f.name)
        populate_file_metadata(file_ins, f, include_content=False)
        enc = file_ins.get("encodingFormat")
        assert isinstance(enc, list)
        # First value is MIME string from magic
        assert "/" in enc[0]
        # Second value is EDAM ContextEntity
        edam_entry = enc[1]
        assert hasattr(edam_entry, "id")
        assert edam_entry.id == "http://edamontology.org/format_2572"

    def test_encoding_format_is_mime_string(self, tmp_path: Path) -> None:
        """File encodingFormat should always contain a MIME string as the first value."""
        f = tmp_path.joinpath("test.txt")
        f.write_text("hello", encoding="utf-8")
        crate = create_base_crate()
        from rocrate.model.file import File

        file_ins = File(crate, f, f.name)
        populate_file_metadata(file_ins, f)
        enc = file_ins.get("encodingFormat")
        first = enc[0] if isinstance(enc, list) else enc
        assert "/" in first
        assert not first.startswith("http")

    def test_nonexistent_file_no_op(self, tmp_path: Path) -> None:
        f = tmp_path.joinpath("nonexistent.txt")
        crate = create_base_crate()
        from rocrate.model.file import File

        file_ins = File(crate, f, f.name)
        populate_file_metadata(file_ins, f)
        assert file_ins.get("sha256") is None


# === generate_ro_crate_metadata (integration) ===


class TestGenerateRoCrateMetadata:
    def test_complete_run_produces_valid_jsonld(self, tmp_path: Path) -> None:
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:10:00",
            wf_params='{"message": "hello"}',
            output_files={"result.txt": "output data"},
            outputs_json=[{"file_name": "result.txt", "file_url": "http://localhost/result.txt"}],
            username="testuser",
            cmd="docker run --rm quay.io/commonwl/cwltool:3.1.0 --outdir /out wf.cwl params.json",
        )
        jsonld = generate_ro_crate_metadata(rd)

        assert "@context" in jsonld
        assert "@graph" in jsonld

        context = jsonld["@context"]
        assert WFRUN_CONTEXT in context
        assert SAPPORO_CONTEXT in context

        graph = jsonld["@graph"]
        ids = {e["@id"] for e in graph}
        assert "./" in ids
        assert "ro-crate-metadata.json" in ids

        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert action["actionStatus"] == "http://schema.org/CompletedActionStatus"
        assert action["exitCode"] == 0
        assert action.get("agent") is not None
        assert action.get("containerImage") is not None

    def test_failed_run_produces_valid_jsonld(self, tmp_path: Path) -> None:
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="1",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:05:00",
            wf_params="{}",
            stderr_content="Error: workflow failed\n",
        )
        jsonld = generate_ro_crate_metadata(rd)

        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert action["actionStatus"] == "http://schema.org/FailedActionStatus"
        assert action["exitCode"] == 1
        assert action.get("error") is not None

    def test_formal_parameters_present(self, tmp_path: Path) -> None:
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params='{"input_file": {"class": "File", "path": "/data/in.fastq"}, "threads": 4}',
            output_files={"out.txt": "result"},
            outputs_json=[],
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]

        fp_entities = [e for e in graph if e.get("@type") == "FormalParameter"]
        assert len(fp_entities) >= 3  # 2 input params + 1 output file

        for fp in fp_entities:
            assert fp.get("conformsTo") == {"@id": BIOSCHEMAS_FORMAL_PARAMETER}

    def test_no_wes_state_in_output(self, tmp_path: Path) -> None:
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert "wesState" not in action

    def test_agent_in_full_generation(self, tmp_path: Path) -> None:
        """Agent should appear as Person entity in full generation."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:10:00",
            wf_params='{"x": 1}',
            username="alice",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert action.get("agent") == {"@id": "#agent-alice"}

        person = next(e for e in graph if e["@id"] == "#agent-alice")
        assert person["@type"] == "Person"
        assert person["name"] == "alice"

    def test_readme_entity_present(self, tmp_path: Path) -> None:
        """README.md entity should be present in the graph."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        readme = next((e for e in graph if e["@id"] == "README.md"), None)
        assert readme is not None
        assert readme["about"] == {"@id": "./"}
        assert readme["encodingFormat"] == "text/markdown"

    def test_bioschemas_workflow_conforms_to(self, tmp_path: Path) -> None:
        """Workflow entity should conformsTo Bioschemas ComputationalWorkflow profile."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        wf_entities = [e for e in graph if isinstance(e.get("@type"), list) and "ComputationalWorkflow" in e["@type"]]
        assert len(wf_entities) >= 1
        wf = wf_entities[0]
        assert wf.get("conformsTo") == {"@id": BIOSCHEMAS_COMPUTATIONAL_WORKFLOW}
        assert wf.get("name") is not None

    def test_software_application_has_url(self, tmp_path: Path) -> None:
        """Known engine SoftwareApplication should have url property."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        sw_entities = [
            e
            for e in graph
            if "SoftwareApplication"
            in (e.get("@type", []) if isinstance(e.get("@type"), list) else [e.get("@type", "")])
        ]
        cwltool_entity = next((e for e in sw_entities if e.get("name") == "cwltool"), None)
        assert cwltool_entity is not None
        assert cwltool_entity["@id"] == "https://github.com/common-workflow-language/cwltool"
        assert cwltool_entity["url"] == "https://github.com/common-workflow-language/cwltool"

    def test_publisher_is_organization(self, tmp_path: Path) -> None:
        """Publisher should be an Organization entity."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        root = next(e for e in graph if e["@id"] == "./")
        publisher_ref = root.get("publisher")
        assert publisher_ref is not None
        publisher_id = publisher_ref["@id"]
        publisher = next(e for e in graph if e["@id"] == publisher_id)
        assert publisher["@type"] == "Organization"
        assert publisher.get("name") is not None

    def test_no_author_on_root_data_entity(self, tmp_path: Path) -> None:
        """Root Data Entity should not have author (execution agent is on CreateAction)."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
            username="alice",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        root = next(e for e in graph if e["@id"] == "./")
        assert root.get("author") is None

    def test_workflow_has_encoding_format(self, tmp_path: Path) -> None:
        """ComputationalWorkflow entity should have encodingFormat."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        wf_entities = [e for e in graph if isinstance(e.get("@type"), list) and "ComputationalWorkflow" in e["@type"]]
        assert len(wf_entities) >= 1
        wf = wf_entities[0]
        assert wf.get("encodingFormat") is not None

    def test_software_entities_present(self, tmp_path: Path) -> None:
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]

        sw_entities = [
            e
            for e in graph
            if "SoftwareApplication"
            in (e.get("@type", []) if isinstance(e.get("@type"), list) else [e.get("@type", "")])
        ]
        names = {e.get("name") for e in sw_entities}
        assert "cwltool" in names
        assert "sapporo" in names


# === _ensure_tz ===


class TestEnsureTz:
    def test_none_returns_none(self) -> None:
        assert _ensure_tz(None) is None

    def test_already_utc_z_converts_to_offset(self) -> None:
        assert _ensure_tz("2024-01-01T00:00:00Z") == "2024-01-01T00:00:00+00:00"

    def test_already_offset(self) -> None:
        assert _ensure_tz("2024-01-01T00:00:00+09:00") == "2024-01-01T00:00:00+09:00"

    def test_missing_tz_appends_offset(self) -> None:
        assert _ensure_tz("2024-01-01T00:00:00") == "2024-01-01T00:00:00+00:00"

    def test_negative_offset(self) -> None:
        assert _ensure_tz("2024-01-01T00:00:00-05:00") == "2024-01-01T00:00:00-05:00"

    def test_lowercase_z_converts_to_offset(self) -> None:
        assert _ensure_tz("2024-01-01T00:00:00z") == "2024-01-01T00:00:00+00:00"


# === Full generation with real data ===

REAL_DATA_DIR = Path(__file__).resolve().parent.parent / "ro-crate" / "ro-crate_dir"


class TestRoCrateFullGeneration:
    """Evaluation tests using real CWL run data and roc-validator."""

    def test_complete_run_with_real_data(self) -> None:
        """Generate RO-Crate from real run data and validate JSON-LD structure."""
        jsonld = generate_ro_crate_metadata(REAL_DATA_DIR)
        graph = jsonld["@graph"]

        # Print full JSON-LD for visual inspection (pytest -s)
        print(json.dumps(jsonld, indent=2, ensure_ascii=False))

        # Root Data Entity
        root = next(e for e in graph if e["@id"] == "./")
        assert "name" in root
        assert "description" in root
        assert isinstance(root["license"], str)
        assert "sapporo" in root["license"].lower()

        # CreateAction
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert action["actionStatus"] == "http://schema.org/CompletedActionStatus"
        assert action.get("instrument") is not None
        assert action.get("object") is not None
        assert action.get("result") is not None

        # ContainerImage
        containers = [e for e in graph if e.get("@type") == "ContainerImage"]
        assert len(containers) >= 1
        container = containers[0]
        assert "sha256" not in container
        assert container["@id"].startswith("https://")
        assert "quay.io" in container["@id"]

        # SoftwareApplication
        sw_entities = [
            e
            for e in graph
            if (isinstance(e.get("@type"), list) and "SoftwareApplication" in e["@type"])
            or e.get("@type") == "SoftwareApplication"
        ]
        assert len(sw_entities) >= 1

        # FormalParameter
        fp_entities = [e for e in graph if e.get("@type") == "FormalParameter"]
        assert len(fp_entities) >= 2  # at least input params
        for fp in fp_entities:
            assert fp.get("conformsTo") == {"@id": BIOSCHEMAS_FORMAL_PARAMETER}

        # Publisher
        assert root.get("publisher") is not None

    def test_failed_run_generation(self, tmp_path: Path) -> None:
        """EXECUTOR_ERROR equivalent: exit_code=1, stderr, no outputs."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="1",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:05:00",
            wf_params='{"input": "test"}',
            stderr_content="ERROR: workflow failed\nTraceback:\n  File ...\nValueError: bad input\n",
            cmd="docker run --rm quay.io/commonwl/cwltool:3.1.0 --outdir /out wf.cwl params.json",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]

        # Print for visual inspection
        print(json.dumps(jsonld, indent=2, ensure_ascii=False))

        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert action["actionStatus"] == "http://schema.org/FailedActionStatus"
        assert action["exitCode"] == 1
        assert "error" in action
        assert "workflow failed" in action["error"]
        # Failed run should have empty result array
        assert action["result"] == []

    def test_timestamps_have_timezone(self, tmp_path: Path) -> None:
        """Timestamps without timezone should get +00:00 appended."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert action["startTime"].endswith("+00:00")
        assert action["endTime"].endswith("+00:00")

    def test_metadata_conforms_to_workflow_profile(self, tmp_path: Path) -> None:
        """Metadata File Descriptor should have conformsTo with Workflow RO-Crate."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        metadata = next(e for e in graph if e["@id"] == "ro-crate-metadata.json")
        conforms = metadata.get("conformsTo")
        assert isinstance(conforms, list)
        conforms_ids = {c["@id"] for c in conforms}
        assert "https://w3id.org/ro/crate/1.1" in conforms_ids
        assert WORKFLOW_PROFILE in conforms_ids

    def test_root_has_required_properties(self, tmp_path: Path) -> None:
        """Root Data Entity must have name, description, license (textual)."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        root = next(e for e in graph if e["@id"] == "./")
        assert root["name"] == f"Sapporo WES run {RUN_ID}"
        assert "Sapporo WES" in root["description"]
        assert isinstance(root["license"], str)
        assert "respective owners" in root["license"]

    def test_metadata_descriptor_has_cc0_license(self, tmp_path: Path) -> None:
        """Metadata Descriptor should have CC0 license."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        metadata = next(e for e in graph if e["@id"] == "ro-crate-metadata.json")
        assert metadata["license"] == {"@id": "https://spdx.org/licenses/CC0-1.0"}

        cc0_entity = next(e for e in graph if e["@id"] == "https://spdx.org/licenses/CC0-1.0")
        assert cc0_entity["@type"] == "CreativeWork"
        assert cc0_entity["name"] == "CC0 1.0 Universal"

    def test_formal_parameter_additional_type_short_form(self, tmp_path: Path) -> None:
        """FormalParameter additionalType should use short form (e.g. 'Integer', 'Text')."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params='{"count": 5, "name": "test", "flag": true}',
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        fp_entities = [e for e in graph if e.get("@type") == "FormalParameter"]
        additional_types = {fp["additionalType"] for fp in fp_entities}
        valid_short_forms = {"Integer", "Float", "Text", "Boolean", "File", "MediaObject"}
        for at in additional_types:
            assert at in valid_short_forms, f"additionalType {at!r} is not a valid short form"

    @pytest.mark.slow
    def test_roc_validator_required_pass(self, tmp_path: Path) -> None:
        """All REQUIRED checks must pass against workflow-run-crate profile."""
        from rocrate_validator.models import Severity, ValidationSettings
        from rocrate_validator.services import validate

        out_dir = tmp_path / "crate"
        out_dir.mkdir()
        # Copy real data dir contents
        import shutil

        for item in REAL_DATA_DIR.iterdir():
            if item.is_dir():
                shutil.copytree(item, out_dir / item.name)
            else:
                shutil.copy2(item, out_dir / item.name)
        # Generate fresh metadata
        generate_ro_crate(str(out_dir))

        settings_obj = ValidationSettings(
            rocrate_uri=str(out_dir),
            profile_identifier="workflow-run-crate",
            requirement_severity=Severity.REQUIRED,
        )
        result = validate(settings_obj)

        # Print issues for debugging
        for issue in result.get_issues():
            print(f"  [{issue.severity}] {issue.message}")

        assert result.passed(), f"REQUIRED violations found: {[i.message for i in result.get_issues()]}"

    @pytest.mark.slow
    def test_roc_validator_recommended_issues(self, tmp_path: Path) -> None:
        """Count RECOMMENDED violations and print them for review."""
        from rocrate_validator.models import Severity, ValidationSettings
        from rocrate_validator.services import validate

        out_dir = tmp_path / "crate"
        out_dir.mkdir()
        import shutil

        for item in REAL_DATA_DIR.iterdir():
            if item.is_dir():
                shutil.copytree(item, out_dir / item.name)
            else:
                shutil.copy2(item, out_dir / item.name)
        generate_ro_crate(str(out_dir))

        settings_obj = ValidationSettings(
            rocrate_uri=str(out_dir),
            profile_identifier="workflow-run-crate",
            requirement_severity=Severity.RECOMMENDED,
        )
        result = validate(settings_obj)

        recommended_issues = [i for i in result.get_issues() if i.severity == Severity.RECOMMENDED]
        print(f"\nRECOMMENDED issues ({len(recommended_issues)}):")
        for issue in recommended_issues:
            print(f"  - {issue.message}")
        # Upper bound: allow some RECOMMENDED violations (sapporo can't satisfy all)
        # Expected warnings: license is textual (not CreativeWork), no author on root,
        # local file WF, CWL File type, test-data-specific (no username),
        # encodingFormat on log/metadata File entities (cmd.txt, system_logs.json, etc.)
        assert len(recommended_issues) <= 25, f"Too many RECOMMENDED issues: {len(recommended_issues)}"


# === generate_ro_crate failure ===


class TestGenerateRoCrateFailure:
    def test_nonexistent_run_dir_raises(self) -> None:
        with pytest.raises((FileNotFoundError, NotADirectoryError)):
            generate_ro_crate("/nonexistent/path")

    def test_missing_run_request_raises(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        with pytest.raises(TypeError):
            generate_ro_crate(str(run_dir))


# === FormalParameter ID collision ===


class TestOutputParameterIdCollision:
    def test_same_name_different_dirs(self, tmp_path: Path) -> None:
        """outputs/dir1/result.txt and outputs/dir2/result.txt get different FormalParameter IDs."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
            output_files={"dir1/result.txt": "a", "dir2/result.txt": "b"},
            outputs_json=[],
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        fp_ids = [
            e["@id"] for e in graph if e.get("@type") == "FormalParameter" and e["@id"].startswith("#param-output-")
        ]
        assert len(fp_ids) == len(set(fp_ids)), f"Duplicate FormalParameter IDs: {fp_ids}"
        assert len(fp_ids) == 2


# === EDAM extension match ===


class TestInspectEdamFormat:
    def test_vcf_gz_matches_vcf_not_gz(self) -> None:
        """.vcf.gz should match VCF, not gzip."""
        result = inspect_edam_format(Path("test.vcf.gz"))
        assert result is not None
        assert "format_3016" in result.url

    def test_fastq_gz_matches_fastq_not_gz(self) -> None:
        result = inspect_edam_format(Path("test.fastq.gz"))
        assert result is not None
        assert "format_1930" in result.url

    def test_plain_gz_matches_gzip(self) -> None:
        result = inspect_edam_format(Path("archive.gz"))
        assert result is not None
        assert "gzip" in result.url

    def test_fq_gz_matches_fastq(self) -> None:
        result = inspect_edam_format(Path("reads.fq.gz"))
        assert result is not None
        assert "format_1930" in result.url

    def test_no_match_returns_none(self) -> None:
        result = inspect_edam_format(Path("unknown.xyz"))
        assert result is None


# === New properties tests ===


class TestNewProperties:
    def _generate(self, tmp_path: Path, **kwargs: Any) -> dict[str, Any]:
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:10:00",
            wf_params='{"x": 1}',
            cmd="docker run --rm quay.io/commonwl/cwltool:3.1.0 --outdir /out wf.cwl params.json",
            stdout_content="log output\n",
            stderr_content="warning\n",
            wf_engine_params_content="--debug",
            **kwargs,
        )
        return generate_ro_crate_metadata(rd)

    def test_date_published_on_root(self, tmp_path: Path) -> None:
        jsonld = self._generate(tmp_path)
        graph = jsonld["@graph"]
        root = next(e for e in graph if e["@id"] == "./")
        assert "datePublished" in root
        assert "T" in root["datePublished"]

    def test_executed_by_on_create_action(self, tmp_path: Path) -> None:
        jsonld = self._generate(tmp_path)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        executed_by = action.get("executedBy")
        assert executed_by is not None
        refs = executed_by if isinstance(executed_by, list) else [executed_by]
        ref_ids = {r["@id"] for r in refs}
        sw_ids = {
            e["@id"]
            for e in graph
            if "SoftwareApplication"
            in (e.get("@type", []) if isinstance(e.get("@type"), list) else [e.get("@type", "")])
        }
        assert ref_ids.issubset(sw_ids)

    def test_subject_of_includes_cmd_and_logs(self, tmp_path: Path) -> None:
        jsonld = self._generate(tmp_path)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        subject_of = action.get("subjectOf", [])
        if not isinstance(subject_of, list):
            subject_of = [subject_of]
        subject_ids = {s["@id"] for s in subject_of}
        assert "stdout.log" in subject_ids
        assert "stderr.log" in subject_ids
        assert "cmd.txt" in subject_ids
        assert "system_logs.json" in subject_ids

    def test_description_is_summary_not_cmd(self, tmp_path: Path) -> None:
        jsonld = self._generate(tmp_path)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        desc = action["description"]
        assert "Executed" in desc
        assert "using" in desc
        assert "docker run" not in desc

    def test_edam_entity_type_is_thing(self, tmp_path: Path) -> None:
        jsonld = self._generate(
            tmp_path,
            output_files={"result.bam": b"\x00" * 100},
            outputs_json=[],
        )
        graph = jsonld["@graph"]
        edam_entities = [e for e in graph if e["@id"].startswith("http://edamontology.org/")]
        assert len(edam_entities) >= 1
        for entity in edam_entities:
            assert entity["@type"] == "Thing"

    def test_ro_crate_conforms_to(self, tmp_path: Path) -> None:
        jsonld = self._generate(tmp_path)
        graph = jsonld["@graph"]
        metadata = next(e for e in graph if e["@id"] == "ro-crate-metadata.json")
        conforms = metadata.get("conformsTo")
        assert isinstance(conforms, list)
        conforms_ids = {c["@id"] for c in conforms}
        assert "https://w3id.org/ro/crate/1.1" in conforms_ids

    def test_wf_engine_params_in_subject_of(self, tmp_path: Path) -> None:
        jsonld = self._generate(tmp_path)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        subject_of = action.get("subjectOf", [])
        if not isinstance(subject_of, list):
            subject_of = [subject_of]
        subject_ids = {s["@id"] for s in subject_of}
        assert "workflow_engine_params.txt" in subject_ids


# === RO-Crate improvements ===


class TestRoCrateImprovements:
    """Tests for RO-Crate generation improvements (WRROC 0.5 compliance)."""

    def test_create_action_id_is_fragment(self, tmp_path: Path) -> None:
        """CreateAction @id should start with '#'."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert action["@id"].startswith("#")

    def test_run_id_from_runtime_info(self, tmp_path: Path) -> None:
        """run_id should be taken from runtime_info.json."""
        custom_run_id = "custom-run-id-12345"
        rd = create_run_dir(tmp_path, RUN_ID, exit_code="0", end_time="2024-01-01T00:10:00", wf_params="{}")
        # Overwrite runtime_info with custom run_id
        from sapporo.config import RUN_DIR_STRUCTURE

        runtime_info = {"run_id": custom_run_id, "sapporo_version": "test", "base_url": "http://localhost:1122"}
        rd.joinpath(RUN_DIR_STRUCTURE["runtime_info"]).write_text(json.dumps(runtime_info), encoding="utf-8")

        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert action["@id"] == f"#{custom_run_id}"
        root = next(e for e in graph if e["@id"] == "./")
        assert custom_run_id in root["name"]

    def test_run_id_fallback_to_dirname(self, tmp_path: Path) -> None:
        """When runtime_info has no run_id, fall back to dirname."""
        rd = create_run_dir(tmp_path, RUN_ID, exit_code="0", end_time="2024-01-01T00:10:00", wf_params="{}")
        # Overwrite runtime_info without run_id
        from sapporo.config import RUN_DIR_STRUCTURE

        runtime_info = {"sapporo_version": "test", "base_url": "http://localhost:1122"}
        rd.joinpath(RUN_DIR_STRUCTURE["runtime_info"]).write_text(json.dumps(runtime_info), encoding="utf-8")

        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        # dirname is the run_id (last component of rd)
        assert action["@id"] == f"#{rd.name}"

    def test_failed_run_has_empty_result_array(self, tmp_path: Path) -> None:
        """Failed run should have result == [] and object as a list."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="1",
            end_time="2024-01-01T00:05:00",
            wf_params="{}",
            stderr_content="Error\n",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert action["result"] == []
        assert isinstance(action["object"], list)

    def test_encoding_format_never_inode(self, tmp_path: Path) -> None:
        """EncodingFormat should never contain 'inode/'."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
            output_files={"empty_file": ""},
            outputs_json=[],
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        for entity in graph:
            enc = entity.get("encodingFormat")
            if enc is None:
                continue
            values = enc if isinstance(enc, list) else [enc]
            for v in values:
                if isinstance(v, str):
                    assert not v.startswith("inode/"), f"Entity {entity['@id']} has inode/ MIME type"

    def test_container_image_has_tag(self, tmp_path: Path) -> None:
        """ContainerImage entity should have a 'tag' property."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
            cmd="docker run --rm quay.io/commonwl/cwltool:3.1.0 --outdir /out wf.cwl",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        containers = [e for e in graph if e.get("@type") == "ContainerImage"]
        assert len(containers) >= 1
        assert containers[0]["tag"] == "3.1.0"

    def test_docker_hub_registry_url(self, tmp_path: Path) -> None:
        """Docker Hub images should use https://docker.io as registry."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
            cmd="docker run --rm nextflow/nextflow:25.10.4 nextflow run wf.nf",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        containers = [e for e in graph if e.get("@type") == "ContainerImage"]
        assert len(containers) >= 1
        assert containers[0]["registry"] == "https://docker.io"

    def test_software_application_uses_software_version(self, tmp_path: Path) -> None:
        """SoftwareApplication should use 'softwareVersion' instead of 'version'."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        sw_entities = [
            e
            for e in graph
            if "SoftwareApplication"
            in (e.get("@type", []) if isinstance(e.get("@type"), list) else [e.get("@type", "")])
        ]
        for sw in sw_entities:
            assert "softwareVersion" in sw, f"SoftwareApplication {sw['@id']} missing softwareVersion"

    def test_ensure_tz_invalid_returns_none(self) -> None:
        """Invalid timestamp should return None."""
        assert _ensure_tz("not-a-timestamp") is None

    def test_count_lines_no_trailing_newline(self, tmp_path: Path) -> None:
        """'hello' (no trailing newline) should count as 1 line."""
        f = tmp_path / "no_newline.txt"
        f.write_text("hello", encoding="utf-8")
        assert count_lines(f) == 1

    def test_count_lines_single_newline(self, tmp_path: Path) -> None:
        r"""'hello\n' should count as 1 line."""
        f = tmp_path / "with_newline.txt"
        f.write_text("hello\n", encoding="utf-8")
        assert count_lines(f) == 1

    def test_count_lines_empty_file(self, tmp_path: Path) -> None:
        """Empty file should count as 0 lines."""
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        assert count_lines(f) == 0


# === Bioinformatics extensions ===


def _make_file_entity(tmp_path: Path, filename: str, content: bytes = b"\x00" * 100) -> Any:
    """Create a File entity with EDAM encoding for testing bioinformatics stats."""
    from rocrate.model.file import File as RoFile

    f = tmp_path / filename
    f.write_bytes(content)
    crate = create_base_crate()
    file_ins = RoFile(crate, f, filename)
    populate_file_metadata(file_ins, f, include_content=False)
    crate.add(file_ins)

    return crate, file_ins


class TestAddMultiqcStats:
    def test_skips_when_docker_not_available(self, tmp_path: Path) -> None:
        """Should return immediately when docker binary is not found."""
        crate = create_base_crate()
        action = crate.add(
            __import__("rocrate.model.contextentity", fromlist=["ContextEntity"]).ContextEntity(
                crate, "#test-action", properties={"@type": "CreateAction"}
            )
        )
        with patch("sapporo.ro_crate.shutil.which", return_value=None):
            add_multiqc_stats(crate, tmp_path, action)
        assert action.get("multiqcStats") is None

    def test_skips_when_docker_fails(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """Should log warning and continue when Docker command fails."""
        from subprocess import CompletedProcess

        from rocrate.model.contextentity import ContextEntity

        crate = create_base_crate()
        action = ContextEntity(crate, "#test-action", properties={"@type": "CreateAction"})
        crate.add(action)

        mocker.patch("sapporo.ro_crate.shutil.which", return_value="/usr/bin/docker")
        mocker.patch(
            "sapporo.ro_crate.subprocess.run",
            return_value=CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"image not found"),
        )

        add_multiqc_stats(crate, tmp_path, action)
        assert action.get("multiqcStats") is None

    def test_adds_stats_when_multiqc_produces_output(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """Should add multiqcStats entity when MultiQC generates stats."""
        from subprocess import CompletedProcess

        from rocrate.model.contextentity import ContextEntity

        crate = create_base_crate()
        action = ContextEntity(crate, "#test-action", properties={"@type": "CreateAction"})
        crate.add(action)

        # Pre-create the multiqc_data directory as Docker would
        multiqc_data = tmp_path / "multiqc_data"
        multiqc_data.mkdir()
        stats_content = [{"sample": "test", "total_reads": 1000}]
        (multiqc_data / "multiqc_general_stats.json").write_text(json.dumps(stats_content), encoding="utf-8")

        mocker.patch("sapporo.ro_crate.shutil.which", return_value="/usr/bin/docker")
        mocker.patch(
            "sapporo.ro_crate.subprocess.run",
            return_value=CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b""),
        )

        add_multiqc_stats(crate, tmp_path, action)
        assert action.get("multiqcStats") is not None
        # multiqc_data directory should be cleaned up
        assert not multiqc_data.exists()
        # Stats file should be moved to run_dir
        assert (tmp_path / "multiqc_general_stats.json").exists()


class TestAddSamtoolsStats:
    _FLAGSTATS_JSON = json.dumps(
        {
            "QC-passed reads": {
                "total": 1000,
                "mapped": 950,
                "duplicates": 50,
            },
            "QC-failed reads": {"total": 0, "mapped": 0, "duplicates": 0},
        }
    ).encode()

    def test_adds_stats_on_success(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """Should add FileStats entity with correct properties."""
        from subprocess import CompletedProcess

        crate, file_ins = _make_file_entity(tmp_path, "test.bam")

        mocker.patch(
            "sapporo.ro_crate.subprocess.run",
            return_value=CompletedProcess(args=[], returncode=0, stdout=self._FLAGSTATS_JSON, stderr=b""),
        )

        add_samtools_stats(crate, file_ins)
        stats_ref = file_ins.get("stats")
        assert stats_ref is not None
        # Resolve the stats entity
        stats_entity = None
        for entity in crate.get_entities():
            types = entity.get("@type", [])
            if not isinstance(types, list):
                types = [types]
            if "FileStats" in types:
                stats_entity = entity
                break
        assert stats_entity is not None
        assert stats_entity["totalReads"] == 1000
        assert stats_entity["mappedReads"] == 950
        assert stats_entity["unmappedReads"] == 50
        assert stats_entity["duplicateReads"] == 50
        assert stats_entity["mappedRate"] == pytest.approx(0.95)
        assert stats_entity["unmappedRate"] == pytest.approx(0.05)
        assert stats_entity["duplicateRate"] == pytest.approx(0.05)

    def test_skips_on_docker_failure(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """Should return without adding stats when Docker fails."""
        from subprocess import CompletedProcess

        crate, file_ins = _make_file_entity(tmp_path, "test.bam")

        mocker.patch(
            "sapporo.ro_crate.subprocess.run",
            return_value=CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"error"),
        )

        add_samtools_stats(crate, file_ins)
        assert file_ins.get("stats") is None

    def test_skips_on_invalid_json(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """Should skip when samtools output is not valid JSON."""
        from subprocess import CompletedProcess

        crate, file_ins = _make_file_entity(tmp_path, "test.bam")

        mocker.patch(
            "sapporo.ro_crate.subprocess.run",
            return_value=CompletedProcess(args=[], returncode=0, stdout=b"not json", stderr=b""),
        )

        add_samtools_stats(crate, file_ins)
        assert file_ins.get("stats") is None

    def test_zero_total_reads_no_division_error(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """Should handle total==0 without ZeroDivisionError."""
        from subprocess import CompletedProcess

        zero_stats = json.dumps(
            {
                "QC-passed reads": {"total": 0, "mapped": 0, "duplicates": 0},
                "QC-failed reads": {"total": 0, "mapped": 0, "duplicates": 0},
            }
        ).encode()
        crate, file_ins = _make_file_entity(tmp_path, "test.bam")

        mocker.patch(
            "sapporo.ro_crate.subprocess.run",
            return_value=CompletedProcess(args=[], returncode=0, stdout=zero_stats, stderr=b""),
        )

        add_samtools_stats(crate, file_ins)
        stats_entity = None
        for entity in crate.get_entities():
            types = entity.get("@type", [])
            if not isinstance(types, list):
                types = [types]
            if "FileStats" in types:
                stats_entity = entity
                break
        assert stats_entity is not None
        assert stats_entity["mappedRate"] == 0.0
        assert stats_entity["unmappedRate"] == 0.0
        assert stats_entity["duplicateRate"] == 0.0

    def test_generated_by_has_samtools_software(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """FileStats should reference samtools SoftwareApplication via generatedBy."""
        from subprocess import CompletedProcess

        crate, file_ins = _make_file_entity(tmp_path, "test.bam")

        mocker.patch(
            "sapporo.ro_crate.subprocess.run",
            return_value=CompletedProcess(args=[], returncode=0, stdout=self._FLAGSTATS_JSON, stderr=b""),
        )

        add_samtools_stats(crate, file_ins)
        stats_entity = None
        for entity in crate.get_entities():
            types = entity.get("@type", [])
            if not isinstance(types, list):
                types = [types]
            if "FileStats" in types:
                stats_entity = entity
                break
        assert stats_entity is not None
        generated_by = stats_entity.get("generatedBy")
        assert generated_by is not None


class TestAddVcftoolsStats:
    _VCFSTATS_OUTPUT = b"""\
$VAR1 = {
          'count' => 42,
          'snp_count' => 30,
          'indel_count' => 12,
        };
"""

    def test_adds_stats_on_success(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """Should add FileStats entity with correct properties."""
        from subprocess import CompletedProcess

        crate, file_ins = _make_file_entity(tmp_path, "test.vcf", content=b"##fileformat=VCFv4.2\n")

        mocker.patch(
            "sapporo.ro_crate.subprocess.run",
            return_value=CompletedProcess(args=[], returncode=0, stdout=self._VCFSTATS_OUTPUT, stderr=b""),
        )

        add_vcftools_stats(crate, file_ins)
        stats_entity = None
        for entity in crate.get_entities():
            types = entity.get("@type", [])
            if not isinstance(types, list):
                types = [types]
            if "FileStats" in types:
                stats_entity = entity
                break
        assert stats_entity is not None
        assert stats_entity["variantCount"] == 42
        assert stats_entity["snpsCount"] == 30
        assert stats_entity["indelsCount"] == 12

    def test_skips_on_docker_failure(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """Should return without adding stats when Docker fails."""
        from subprocess import CompletedProcess

        crate, file_ins = _make_file_entity(tmp_path, "test.vcf", content=b"##fileformat=VCFv4.2\n")

        mocker.patch(
            "sapporo.ro_crate.subprocess.run",
            return_value=CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"error"),
        )

        add_vcftools_stats(crate, file_ins)
        assert file_ins.get("stats") is None

    def test_generated_by_has_vcftools_software(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """FileStats should reference vcftools SoftwareApplication via generatedBy."""
        from subprocess import CompletedProcess

        crate, file_ins = _make_file_entity(tmp_path, "test.vcf", content=b"##fileformat=VCFv4.2\n")

        mocker.patch(
            "sapporo.ro_crate.subprocess.run",
            return_value=CompletedProcess(args=[], returncode=0, stdout=self._VCFSTATS_OUTPUT, stderr=b""),
        )

        add_vcftools_stats(crate, file_ins)
        stats_entity = None
        for entity in crate.get_entities():
            types = entity.get("@type", [])
            if not isinstance(types, list):
                types = [types]
            if "FileStats" in types:
                stats_entity = entity
                break
        assert stats_entity is not None
        generated_by = stats_entity.get("generatedBy")
        assert generated_by is not None


class TestAddFileStats:
    def test_skips_when_docker_not_available(self, tmp_path: Path) -> None:
        """Should return immediately when docker binary is not found."""
        crate, file_ins = _make_file_entity(tmp_path, "test.bam")
        with patch("sapporo.ro_crate.shutil.which", return_value=None):
            add_file_stats(crate, file_ins)
        assert file_ins.get("stats") is None

    def test_dispatches_to_samtools_for_bam(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """Should call add_samtools_stats for BAM files."""
        crate, file_ins = _make_file_entity(tmp_path, "test.bam")
        mocker.patch("sapporo.ro_crate.shutil.which", return_value="/usr/bin/docker")
        mock_samtools = mocker.patch("sapporo.ro_crate.add_samtools_stats")
        mock_vcftools = mocker.patch("sapporo.ro_crate.add_vcftools_stats")

        add_file_stats(crate, file_ins)
        mock_samtools.assert_called_once_with(crate, file_ins)
        mock_vcftools.assert_not_called()

    def test_dispatches_to_vcftools_for_vcf(self, tmp_path: Path, mocker: "MockerFixture") -> None:
        """Should call add_vcftools_stats for VCF files."""
        crate, file_ins = _make_file_entity(tmp_path, "test.vcf", content=b"##fileformat=VCFv4.2\n")
        mocker.patch("sapporo.ro_crate.shutil.which", return_value="/usr/bin/docker")
        mock_samtools = mocker.patch("sapporo.ro_crate.add_samtools_stats")
        mock_vcftools = mocker.patch("sapporo.ro_crate.add_vcftools_stats")

        add_file_stats(crate, file_ins)
        mock_vcftools.assert_called_once_with(crate, file_ins)
        mock_samtools.assert_not_called()


# === Robustness tests ===


class TestRobustness:
    def test_unknown_workflow_type_does_not_crash(self, tmp_path: Path) -> None:
        """Completely unknown workflow_type should produce valid metadata with generic ComputerLanguage."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            run_request_dict={
                "workflow_params": "{}",
                "workflow_type": "UNKNOWN_LANG",
                "workflow_type_version": "1.0",
                "tags": {},
                "workflow_engine": "cwltool",
                "workflow_engine_version": None,
                "workflow_engine_parameters": None,
                "workflow_url": "https://example.com/wf.unknown",
                "workflow_attachment": [],
                "workflow_attachment_obj": [],
            },
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        assert "@graph" in jsonld

        lang_entities = [e for e in graph if e.get("@id") == "UNKNOWN_LANG"]
        assert len(lang_entities) == 1
        assert lang_entities[0]["name"] == "UNKNOWN_LANG"

    def test_unknown_workflow_engine_does_not_crash(self) -> None:
        """Unknown engine name should produce SoftwareApplication with fragment identifier."""
        crate = create_base_crate()
        sw = find_or_generate_software_ins(crate, "my_custom_engine", "0.1.0")
        assert sw["@id"] == "#my_custom_engine"
        assert sw["name"] == "my_custom_engine"
        assert sw.get("url") is None

    def test_missing_local_workflow_file_does_not_crash(self, tmp_path: Path) -> None:
        """Local workflow file not on disk should not crash, uses URL string as identifier."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            run_request_dict={
                "workflow_params": "{}",
                "workflow_type": "CWL",
                "workflow_type_version": "v1.0",
                "tags": {},
                "workflow_engine": "cwltool",
                "workflow_engine_version": None,
                "workflow_engine_parameters": None,
                "workflow_url": "nonexistent_wf.cwl",
                "workflow_attachment": [],
                "workflow_attachment_obj": [],
            },
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        # Do NOT create the file - it should fallback gracefully
        jsonld = generate_ro_crate_metadata(rd)
        assert "@graph" in jsonld
        graph = jsonld["@graph"]
        wf_entities = [e for e in graph if isinstance(e.get("@type"), list) and "ComputationalWorkflow" in e["@type"]]
        assert len(wf_entities) >= 1
        assert wf_entities[0]["@id"] == "nonexistent_wf.cwl"

    def test_missing_run_request_raises_clear_error(self, tmp_path: Path) -> None:
        """Missing run_request.json should raise TypeError with descriptive message."""
        rd = tmp_path / "aa" / "aabbccdd"
        rd.mkdir(parents=True)
        with pytest.raises(TypeError, match=r"run_request\.json is missing or invalid"):
            generate_ro_crate_metadata(rd)

    def test_non_numeric_exit_code(self, tmp_path: Path) -> None:
        """Non-numeric exit_code should not crash; sets FailedActionStatus without exitCode."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="SIGKILL",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert action["actionStatus"] == "http://schema.org/FailedActionStatus"
        assert "exitCode" not in action

    def test_empty_outputs_dir(self, tmp_path: Path) -> None:
        """Empty outputs directory should produce result == []."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
        )
        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        assert action["result"] == []

    def test_output_file_disappeared(self, tmp_path: Path) -> None:
        """Output file that disappears after listing should be skipped."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
            output_files={"result.txt": "output data", "vanished.txt": "will disappear"},
            outputs_json=[],
        )
        # Remove one output file to simulate disappearance
        from sapporo.config import RUN_DIR_STRUCTURE

        rd.joinpath(RUN_DIR_STRUCTURE["outputs_dir"], "vanished.txt").unlink()

        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        result = action.get("result", [])
        if not isinstance(result, list):
            result = [result]
        result_ids = {r["@id"] if isinstance(r, dict) else r.id for r in result}
        assert any("result.txt" in rid for rid in result_ids)
        assert not any("vanished.txt" in rid for rid in result_ids)


# === Robustness PBT tests ===


class TestRobustnessPBT:
    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_pbt_any_workflow_type_does_not_crash(self, wf_type: str) -> None:
        """Any workflow_type string should not crash resolve_workflow_language."""
        crate = create_base_crate()
        req = make_run_request_form(workflow_type=wf_type, workflow_type_version="1.0")
        lang = resolve_workflow_language(crate, req)
        assert lang is not None

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_pbt_any_engine_name_does_not_crash(self, engine_name: str) -> None:
        """Any engine name should not crash find_or_generate_software_ins."""
        crate = create_base_crate()
        sw = find_or_generate_software_ins(crate, engine_name, "1.0")
        assert sw is not None
        assert sw["name"] == engine_name

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=50)
    def test_pbt_any_timestamp_does_not_crash(self, ts: str) -> None:
        """Any string should not crash _ensure_tz (returns str or None)."""
        result = _ensure_tz(ts)
        assert result is None or isinstance(result, str)

    @given(st.text(min_size=0, max_size=500))
    @settings(max_examples=50)
    def test_pbt_extract_docker_image_never_crashes(self, cmd: str) -> None:
        """Any string should not crash extract_docker_image."""
        result = extract_docker_image(cmd)
        assert result is None or (isinstance(result, tuple) and len(result) == 2)


# === Edge case tests ===


class TestEdgeCases:
    def test_wdl_workflow_type(self) -> None:
        """WDL should produce correct ComputerLanguage even though not in LANG_MAP."""
        crate = create_base_crate()
        req = make_run_request_form(workflow_type="WDL", workflow_type_version="1.0")
        lang = resolve_workflow_language(crate, req)
        assert lang["name"] == "Workflow Description Language"
        assert lang["@id"] == "https://openwdl.org"
        assert lang.get("alternateName") == "WDL"

    def test_symlink_output_file(self, tmp_path: Path) -> None:
        """Symlinked output file should be followed and included."""
        rd = create_run_dir(
            tmp_path,
            RUN_ID,
            exit_code="0",
            end_time="2024-01-01T00:10:00",
            wf_params="{}",
            output_files={"real_output.txt": "real content"},
            outputs_json=[],
        )
        from sapporo.config import RUN_DIR_STRUCTURE

        outputs_dir = rd.joinpath(RUN_DIR_STRUCTURE["outputs_dir"])
        real_file = outputs_dir.joinpath("real_output.txt")
        symlink_path = outputs_dir.joinpath("link.txt")
        symlink_path.symlink_to(real_file)

        jsonld = generate_ro_crate_metadata(rd)
        graph = jsonld["@graph"]
        action = next(e for e in graph if e.get("@type") == "CreateAction")
        result = action.get("result", [])
        if not isinstance(result, list):
            result = [result]
        # Should have at least real_output.txt (link.txt resolves to same file, may be deduplicated)
        assert len(result) >= 1

    def test_binary_file_metadata_does_not_crash(self, tmp_path: Path) -> None:
        """Binary file should not crash populate_file_metadata."""
        f = tmp_path.joinpath("binary.bin")
        f.write_bytes(bytes(range(256)))
        crate = create_base_crate()
        from rocrate.model.file import File as RoFile

        file_ins = RoFile(crate, f, f.name)
        populate_file_metadata(file_ins, f)
        assert file_ins.get("sha256") is not None
        assert file_ins.get("contentSize") == 256
        enc = file_ins.get("encodingFormat")
        first = enc[0] if isinstance(enc, list) else enc
        assert isinstance(first, str)
