import contextlib
import hashlib
import io
import json
import logging
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from sapporo.config import RunDirStructureKeys

import magic
from fastapi import UploadFile
from pydantic import BaseModel, TypeAdapter
from rocrate.model.computationalworkflow import ComputationalWorkflow
from rocrate.model.computerlanguage import LANG_MAP, ComputerLanguage
from rocrate.model.computerlanguage import get_lang as ro_crate_get_lang
from rocrate.model.contextentity import ContextEntity
from rocrate.model.creativework import CreativeWork
from rocrate.model.file import File
from rocrate.model.metadata import WORKFLOW_PROFILE
from rocrate.model.softwareapplication import SoftwareApplication
from rocrate.rocrate import ROCrate
from rocrate.utils import get_norm_value

from sapporo.config import RUN_DIR_STRUCTURE
from sapporo.schemas import FileObject, RunRequestForm
from sapporo.utils import read_run_dir_file

# === Constants ===

PROCESS_RUN_PROFILE = "https://w3id.org/ro/wfrun/process/0.5"
WORKFLOW_RUN_PROFILE = "https://w3id.org/ro/wfrun/workflow/0.5"
WFRUN_CONTEXT = "https://w3id.org/ro/terms/workflow-run/context"
SAPPORO_CONTEXT = "https://w3id.org/ro/terms/sapporo"
BIOSCHEMAS_FORMAL_PARAMETER = "https://bioschemas.org/profiles/FormalParameter/1.0-RELEASE"
BIOSCHEMAS_COMPUTATIONAL_WORKFLOW = "https://bioschemas.org/profiles/ComputationalWorkflow/1.0-RELEASE"

_STDERR_TAIL_LINES = 20
_DOCKER_IMAGE_RE = re.compile(r"(?:^|\s)([\w.-]+/[\w.-]+(?:/[\w.-]+)?:[\w.+-]+)")
_WF_MIME_TYPE: dict[str, str] = {
    "CWL": "application/x-yaml",
    "WDL": "text/plain",
    "NFL": "text/x-groovy",
    "SMK": "text/x-python",
}


class EDAM(BaseModel):
    url: str
    name: str


EDAM_MAPPING: dict[str, EDAM] = {
    ".bam": EDAM(
        url="http://edamontology.org/format_2572",
        name="BAM format, the binary, BGZF-formatted compressed version of SAM format for alignment of nucleotide sequences (e.g. sequencing reads) to (a) reference sequence(s). May contain base-call and alignment qualities and other data.",
    ),
    ".bb": EDAM(
        url="http://edamontology.org/format_3004",
        name="bigBed format for large sequence annotation tracks, similar to textual BED format.",
    ),
    ".bed": EDAM(
        url="http://edamontology.org/format_3003",
        name="Browser Extensible Data (BED) format of sequence annotation track, typically to be displayed in a genome browser.",
    ),
    ".bw": EDAM(
        url="http://edamontology.org/format_3006",
        name="bigWig format for large sequence annotation tracks that consist of a value for each sequence position. Similar to textual WIG format.",
    ),
    ".fa": EDAM(url="http://edamontology.org/format_1929", name="FASTA format including NCBI-style IDs."),
    ".fasta": EDAM(url="http://edamontology.org/format_1929", name="FASTA format including NCBI-style IDs."),
    ".fastq": EDAM(url="http://edamontology.org/format_1930", name="FASTQ short read format ignoring quality scores."),
    ".fastq.gz": EDAM(
        url="http://edamontology.org/format_1930", name="FASTQ short read format ignoring quality scores."
    ),
    ".fq": EDAM(url="http://edamontology.org/format_1930", name="FASTQ short read format ignoring quality scores."),
    ".fq.gz": EDAM(url="http://edamontology.org/format_1930", name="FASTQ short read format ignoring quality scores."),
    ".gtf": EDAM(
        url="http://edamontology.org/format_2306", name="Gene Transfer Format (GTF), a restricted version of GFF."
    ),
    ".gff": EDAM(
        url="http://edamontology.org/format_1975", name="Generic Feature Format version 3 (GFF3) of sequence features."
    ),
    ".sam": EDAM(
        url="http://edamontology.org/format_2573",
        name="Sequence Alignment/Map (SAM) format for alignment of nucleotide sequences (e.g. sequencing reads) to (a) reference sequence(s). May contain base-call and alignment qualities and other data.",
    ),
    ".vcf": EDAM(
        url="http://edamontology.org/format_3016",
        name="Variant Call Format (VCF) for sequence variation (indels, polymorphisms, structural variation).",
    ),
    ".vcf.gz": EDAM(
        url="http://edamontology.org/format_3016",
        name="Variant Call Format (VCF) for sequence variation (indels, polymorphisms, structural variation).",
    ),
    ".wig": EDAM(
        url="http://edamontology.org/format_3005",
        name="Wiggle format (WIG) of a sequence annotation track that consists of a value for each sequence position. Typically to be displayed in a genome browser.",
    ),
    ".html": EDAM(url="https://www.iana.org/assignments/media-types/text/html", name="HTML"),
    ".json": EDAM(url="https://www.iana.org/assignments/media-types/application/json", name="JSON"),
    ".csv": EDAM(url="https://www.iana.org/assignments/media-types/text/csv", name="CSV"),
    ".tsv": EDAM(url="https://www.iana.org/assignments/media-types/text/tab-separated-values", name="TSV"),
    ".txt": EDAM(url="https://www.iana.org/assignments/media-types/text/plain", name="Plain text"),
    ".log": EDAM(url="https://www.iana.org/assignments/media-types/text/plain", name="Plain text"),
    ".md": EDAM(url="https://www.iana.org/assignments/media-types/text/markdown", name="Markdown"),
    ".yml": EDAM(url="https://www.iana.org/assignments/media-types/application/x-yaml", name="YAML"),
    ".yaml": EDAM(url="https://www.iana.org/assignments/media-types/application/x-yaml", name="YAML"),
    ".cwl": EDAM(url="https://www.iana.org/assignments/media-types/application/x-yaml", name="YAML"),
    ".wdl": EDAM(url="https://www.iana.org/assignments/media-types/text/plain", name="Plain text"),
    ".nf": EDAM(url="https://www.iana.org/assignments/media-types/text/plain", name="Plain text"),
    ".smk": EDAM(url="https://www.iana.org/assignments/media-types/text/plain", name="Plain text"),
    ".zip": EDAM(url="https://www.iana.org/assignments/media-types/application/zip", name="ZIP"),
    ".gz": EDAM(url="https://www.iana.org/assignments/media-types/application/gzip", name="gzip"),
}


# === Utility functions ===


def load_run_request(obj: dict[str, Any]) -> RunRequestForm:
    wf_attachment = [
        UploadFile(
            file=io.BytesIO(b""),
            filename=f["filename"],
            headers=f["headers"],
            size=f["size"],
        )
        for f in obj["workflow_attachment"]
    ]
    obj["workflow_attachment"] = wf_attachment

    return RunRequestForm.model_validate(obj)


def count_lines(file_path: Path) -> int:
    block_size = 65536
    count = 0
    last_char = ""
    with file_path.open("r") as f:
        while True:
            buffer = f.read(block_size)
            if not buffer:
                break
            count += buffer.count("\n")
            last_char = buffer[-1]
    if last_char and last_char != "\n":
        count += 1
    return count


def compute_sha256(file_path: Path) -> str:
    block_size = 65536
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        while True:
            buffer = f.read(block_size)
            if not buffer:
                break
            sha256.update(buffer)

    return sha256.hexdigest()


def inspect_edam_format(file_path: Path) -> EDAM | None:
    for ext in sorted(EDAM_MAPPING, key=len, reverse=True):
        if file_path.name.endswith(ext):
            return EDAM_MAPPING[ext]

    return None


def infer_parameter_type(value: Any) -> str:
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, int):
        return "Integer"
    if isinstance(value, float):
        return "Float"
    if isinstance(value, dict) and value.get("class") == "File":
        return "File"

    return "Text"


def extract_docker_image(cmd_txt: str) -> tuple[str, str] | None:
    """Extract Docker image name and tag from a cmd.txt string.

    Returns (image_name, tag) or None if no Docker image found.
    Looks for patterns like ``org/image:tag`` or ``registry/org/image:tag``.
    """
    if "docker" not in cmd_txt:
        return None
    match = _DOCKER_IMAGE_RE.search(cmd_txt)
    if match is None:
        return None
    image_str = match.group(1)
    name, tag = image_str.rsplit(":", 1)

    return name, tag


def _ensure_tz(timestamp: str | None) -> str | None:
    """Normalize an ISO 8601 timestamp to use ``+HH:MM`` offset (never ``Z``).

    roc-validator only accepts ``+HH:MM`` / ``-HH:MM`` offsets.
    """
    if timestamp is None:
        return None
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00").replace("z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        logging.getLogger("sapporo").warning("Invalid timestamp format: %s", timestamp)
        return None


# === Base crate ===


def create_base_crate() -> ROCrate:
    """Create a new RO-Crate with WRROC 0.5 profiles."""
    crate = ROCrate(init=False, gen_preview=False)

    crate.metadata.extra_contexts.append(WFRUN_CONTEXT)
    crate.metadata.extra_contexts.append(SAPPORO_CONTEXT)
    crate.metadata.extra_terms = {"executedBy": f"{SAPPORO_CONTEXT}#executedBy"}

    crate.root_dataset.append_to(
        "conformsTo",
        [
            {"@id": PROCESS_RUN_PROFILE},
            {"@id": WORKFLOW_RUN_PROFILE},
            {"@id": WORKFLOW_PROFILE},
        ],
    )

    for profile_id, name, version in [
        (PROCESS_RUN_PROFILE, "Process Run Crate", "0.5"),
        (WORKFLOW_RUN_PROFILE, "Workflow Run Crate", "0.5"),
        (WORKFLOW_PROFILE, "Workflow RO-Crate", "1.0"),
    ]:
        crate.add(CreativeWork(crate, profile_id, properties={"name": name, "version": version}))

    # Metadata File Descriptor conformsTo (RO-Crate 1.1 + Workflow RO-Crate 1.0)
    crate.metadata["conformsTo"] = [
        {"@id": "https://w3id.org/ro/crate/1.1"},
        {"@id": WORKFLOW_PROFILE},
    ]

    # Metadata File Descriptor license: CC0 (auto-generated metadata)
    cc0 = ContextEntity(
        crate,
        "https://spdx.org/licenses/CC0-1.0",
        properties={
            "@type": "CreativeWork",
            "name": "CC0 1.0 Universal",
            "url": "https://creativecommons.org/publicdomain/zero/1.0/",
        },
    )
    crate.add(cc0)
    crate.metadata["license"] = cc0

    return crate


# === Workflow language ===


def resolve_workflow_language(crate: ROCrate, run_request: RunRequestForm) -> ComputerLanguage:
    """Generate a ComputerLanguage instance for the workflow type.

    wf_type: "CWL", "WDL", "NFL", "SMK" or others
    wf_type_version: str
    """
    wf_type = run_request.workflow_type
    wf_type_version = run_request.workflow_type_version
    if re.search("^v", wf_type_version):
        wf_type_version = wf_type_version[1:]

    lang_type_for_ro_crate = wf_type
    if wf_type.lower() == "nfl":
        lang_type_for_ro_crate = "nextflow"
    elif wf_type.lower() == "smk":
        lang_type_for_ro_crate = "snakemake"

    if lang_type_for_ro_crate.lower() in LANG_MAP:
        lang_ins = ro_crate_get_lang(crate, lang_type_for_ro_crate, wf_type_version)
        for filed in ["identifier", "url"]:
            id_ = get_norm_value(lang_ins, filed)[0]
            cxt = ContextEntity(
                crate,
                id_,
                properties={
                    "@type": ["WebPage"],
                },
            )
            crate.add(cxt)
    elif wf_type.lower() == "wdl":
        id_ = "https://openwdl.org"
        lang_ins = ComputerLanguage(
            crate,
            id_,
            properties={
                "name": "Workflow Description Language",
                "alternateName": "WDL",
                "version": wf_type_version,
            },
        )
        ctx = ContextEntity(
            crate,
            id_,
            properties={
                "@type": ["WebPage"],
            },
        )
        lang_ins.append_to("identifier", ctx, compact=True)
        lang_ins.append_to("url", ctx, compact=True)
        crate.add(ctx)
    else:
        lang_ins = ComputerLanguage(
            crate,
            wf_type,
            properties={
                "name": wf_type,
                "version": wf_type_version,
            },
        )

    crate.add(lang_ins)

    return lang_ins


# === Entity builders ===


def add_workflow_entity(crate: ROCrate, run_dir: Path, run_request: RunRequestForm) -> ComputationalWorkflow:
    """Add a ComputationalWorkflow entity to the RO-Crate."""
    wf_url = run_request.workflow_url
    wf_url_parts = urlsplit(wf_url)
    if wf_url_parts.scheme in ["http", "https"]:
        wf_ins = ComputationalWorkflow(crate, wf_url)
    else:
        try:
            wf_file_path = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"], wf_url).resolve(strict=True)
            wf_ins = ComputationalWorkflow(crate, wf_file_path, wf_file_path.relative_to(run_dir))
        except FileNotFoundError:
            wf_ins = ComputationalWorkflow(crate, wf_url)

    crate.add(wf_ins)
    crate.mainEntity = wf_ins
    wf_ins.lang = resolve_workflow_language(crate, run_request)

    # Bioschemas ComputationalWorkflow profile
    bioschemas_profile = CreativeWork(
        crate,
        BIOSCHEMAS_COMPUTATIONAL_WORKFLOW,
        properties={"name": "ComputationalWorkflow", "version": "1.0-RELEASE"},
    )
    crate.add(bioschemas_profile)
    wf_ins["conformsTo"] = {"@id": BIOSCHEMAS_COMPUTATIONAL_WORKFLOW}

    # Extract workflow name from URL
    wf_path = wf_url_parts.path or wf_url
    wf_name = Path(wf_path).name or wf_url
    wf_ins["name"] = wf_name

    if wf_url_parts.scheme in ["http", "https"]:
        wf_ins["url"] = wf_url

    if run_request.workflow_type_version:
        wf_ins["version"] = run_request.workflow_type_version

    mime_type = _WF_MIME_TYPE.get(run_request.workflow_type.upper(), "text/plain")
    wf_ins["encodingFormat"] = mime_type

    return wf_ins


def add_agent(crate: ROCrate, run_dir: Path) -> ContextEntity | None:
    """Add a Person entity from username.txt."""
    username = read_run_dir_file(run_dir, "username", one_line=True)
    if not username:
        return None

    agent = ContextEntity(
        crate,
        f"#agent-{username}",
        properties={
            "@type": "Person",
            "name": username,
        },
    )
    crate.add(agent)

    return agent


def add_container_image(crate: ROCrate, run_dir: Path) -> ContextEntity | None:
    """Add a ContainerImage entity extracted from cmd.txt."""
    cmd_txt = read_run_dir_file(run_dir, "cmd", raw=True)
    if not cmd_txt:
        return None
    result = extract_docker_image(cmd_txt)
    if result is None:
        return None

    image_name, image_tag = result
    first_part = image_name.split("/")[0]
    has_registry = "." in first_part
    if has_registry:
        container_id = f"https://{image_name}"
        registry = f"https://{first_part}"
    else:
        container_id = f"https://docker.io/{image_name}"
        registry = "https://docker.io"
    container = ContextEntity(
        crate,
        container_id,
        properties={
            "@type": "ContainerImage",
            "name": f"{image_name}:{image_tag}",
            "additionalType": {"@id": "https://w3id.org/ro/terms/workflow-run#DockerImage"},
            "registry": registry,
            "tag": image_tag,
        },
    )
    crate.add(container)

    return container


def add_software_entities(
    crate: ROCrate, run_request: RunRequestForm, run_dir: Path
) -> tuple[SoftwareApplication | None, SoftwareApplication | None]:
    """Add SoftwareApplication entities for the workflow engine and sapporo."""
    engine_name = run_request.workflow_engine
    engine_ins = find_or_generate_software_ins(crate, engine_name, run_request.workflow_engine_version or "")

    sapporo_ins: SoftwareApplication | None = None
    runtime_info = read_run_dir_file(run_dir, "runtime_info")
    if runtime_info and isinstance(runtime_info, dict):
        sapporo_version = runtime_info.get("sapporo_version", "")
        sapporo_ins = find_or_generate_software_ins(crate, "sapporo", str(sapporo_version))

    return engine_ins, sapporo_ins


def _make_formal_parameter(
    crate: ROCrate,
    param_id: str,
    name: str,
    additional_type: str,
) -> ContextEntity:
    fp = ContextEntity(
        crate,
        param_id,
        properties={
            "@type": "FormalParameter",
            "name": name,
            "additionalType": additional_type,
            "conformsTo": {"@id": BIOSCHEMAS_FORMAL_PARAMETER},
        },
    )
    crate.add(fp)

    return fp


def add_input_parameters(
    crate: ROCrate,
    wf: ComputationalWorkflow,
    action: ContextEntity,
    run_dir: Path,
    run_request: RunRequestForm,
) -> None:
    """Add input parameters (from workflow_params.json) as FormalParameter + PropertyValue."""
    wf_params_path = run_dir.joinpath(RUN_DIR_STRUCTURE["wf_params"])
    if not wf_params_path.exists():
        return

    try:
        with wf_params_path.open("r", encoding="utf-8") as f:
            params = json.load(f)
    except (json.JSONDecodeError, OSError):
        params = None

    if not isinstance(params, dict):
        raw_content = read_run_dir_file(run_dir, "wf_params", raw=True) or ""
        fp = _make_formal_parameter(crate, "#param-input-params", "workflow_params", "Text")
        wf.append_to("input", fp, compact=True)
        pv = ContextEntity(
            crate,
            "#pv-workflow-params",
            properties={
                "@type": "PropertyValue",
                "name": "workflow_params",
                "value": raw_content,
                "exampleOfWork": {"@id": fp.id},
            },
        )
        crate.add(pv)
        fp.append_to("workExample", pv, compact=True)
        action.append_to("object", pv, compact=True)

        return

    for key, value in params.items():
        safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
        param_type = infer_parameter_type(value)
        fp = _make_formal_parameter(crate, f"#param-input-{safe_key}", key, param_type)
        wf.append_to("input", fp, compact=True)

        if param_type == "File" and isinstance(value, dict):
            file_path_str = value.get("path") or value.get("location", "")
            pv = ContextEntity(
                crate,
                f"#pv-{safe_key}",
                properties={
                    "@type": "PropertyValue",
                    "name": key,
                    "value": file_path_str,
                    "exampleOfWork": {"@id": fp.id},
                },
            )
        else:
            serialized = json.dumps(value) if isinstance(value, (dict, list)) else value
            pv = ContextEntity(
                crate,
                f"#pv-{safe_key}",
                properties={
                    "@type": "PropertyValue",
                    "name": key,
                    "value": serialized,
                    "exampleOfWork": {"@id": fp.id},
                },
            )
        crate.add(pv)
        fp.append_to("workExample", pv, compact=True)
        action.append_to("object", pv, compact=True)


def add_input_file_entities(
    crate: ROCrate,
    wf: ComputationalWorkflow,
    action: ContextEntity,
    run_dir: Path,
    run_request: RunRequestForm,
) -> None:
    """Add input file entities from workflow_attachment."""
    main_wf_id = crate.mainEntity["@id"]

    for attached_file in run_request.workflow_attachment:
        source = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"], str(attached_file.filename))
        dest = source.relative_to(run_dir)
        if str(dest) == str(main_wf_id):
            continue
        file_ins = File(crate, source, dest, properties={"@type": "File"})
        populate_file_metadata(file_ins, source, include_content=False)
        crate.add(file_ins)

        safe_path = re.sub(r"[^a-zA-Z0-9_/-]", "_", str(attached_file.filename))
        fp = _make_formal_parameter(crate, f"#param-input-file-{safe_path}", str(attached_file.filename), "File")
        wf.append_to("input", fp, compact=True)
        file_ins.append_to("exampleOfWork", fp, compact=True)
        fp.append_to("workExample", file_ins, compact=True)
        action.append_to("object", file_ins, compact=True)

    for attached_item in run_request.workflow_attachment_obj:
        source = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"], attached_item.file_name)
        dest = source.relative_to(run_dir)
        if str(dest) == str(main_wf_id):
            continue
        file_ins = File(crate, source, dest, properties={"@type": "File", "url": attached_item.file_url})
        populate_file_metadata(file_ins, source, include_content=False)
        crate.add(file_ins)

        safe_path = re.sub(r"[^a-zA-Z0-9_/-]", "_", attached_item.file_name)
        fp = _make_formal_parameter(crate, f"#param-input-obj-{safe_path}", attached_item.file_name, "File")
        wf.append_to("input", fp, compact=True)
        file_ins.append_to("exampleOfWork", fp, compact=True)
        fp.append_to("workExample", file_ins, compact=True)
        action.append_to("object", file_ins, compact=True)


outputs_adapter = TypeAdapter(list[FileObject])


def add_output_file_entities(
    crate: ROCrate,
    wf: ComputationalWorkflow,
    action: ContextEntity,
    run_dir: Path,
) -> None:
    """Add output file entities from outputs/ directory."""
    outputs = outputs_adapter.validate_python(read_run_dir_file(run_dir, "outputs") or [])
    outputs_dir_path = run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"])

    for source in sorted(outputs_dir_path.glob("**/*")):
        if source.is_dir():
            continue

        try:
            file_apath = source.resolve(strict=True)
        except FileNotFoundError:
            continue
        file_rpath = file_apath.relative_to(run_dir)

        file_ins = File(crate, file_apath, file_rpath, properties={"@type": "File"})
        populate_file_metadata(file_ins, file_apath)

        if outputs is not None:
            output_dir_dest = file_apath.relative_to(outputs_dir_path)
            for output in outputs:
                if str(output.file_name) == str(output_dir_dest):
                    file_ins["url"] = output.file_url

        add_file_stats(crate, file_ins)

        safe_path = re.sub(r"[^a-zA-Z0-9_/-]", "_", str(file_rpath))
        fp = _make_formal_parameter(crate, f"#param-output-{safe_path}", file_rpath.name, "File")
        wf.append_to("output", fp, compact=True)
        file_ins.append_to("exampleOfWork", fp, compact=True)
        fp.append_to("workExample", file_ins, compact=True)
        action.append_to("result", file_ins, compact=True)
        crate.add(file_ins)


def add_log_file_entities(crate: ROCrate, action: ContextEntity, run_dir: Path) -> None:
    """Add log and metadata file entities as subjectOf the CreateAction."""
    log_files: list[tuple[RunDirStructureKeys, str]] = [
        ("stdout", "Sapporo stdout"),
        ("stderr", "Sapporo stderr"),
        ("cmd", "Execution command"),
        ("system_logs", "System logs"),
        ("wf_engine_params", "Workflow engine parameters"),
    ]
    for key, name in log_files:
        source = run_dir.joinpath(RUN_DIR_STRUCTURE[key])
        if source.exists() is False:
            continue
        dest = source.relative_to(run_dir)
        file_ins = File(crate, source, dest, properties={"name": name})
        populate_file_metadata(file_ins, source)
        action.append_to("subjectOf", file_ins)
        crate.add(file_ins)


def add_create_action(
    crate: ROCrate,
    wf: ComputationalWorkflow,
    run_dir: Path,
    run_request: RunRequestForm,
    run_id: str,
) -> ContextEntity:
    """Create and populate the main CreateAction entity."""
    action = ContextEntity(
        crate,
        identifier=f"#{run_id}",
        properties={"@type": "CreateAction", "name": f"Sapporo workflow run {run_id}"},
    )
    action.append_to("instrument", wf, compact=True)
    crate.root_dataset.append_to("mentions", action)

    # Timestamps
    action["startTime"] = _ensure_tz(read_run_dir_file(run_dir, "start_time", one_line=True))
    action["endTime"] = _ensure_tz(read_run_dir_file(run_dir, "end_time", one_line=True))

    # Status
    exit_code_str = read_run_dir_file(run_dir, "exit_code", one_line=True)
    if exit_code_str is not None:
        try:
            action["exitCode"] = int(exit_code_str)
        except ValueError:
            action["actionStatus"] = "http://schema.org/FailedActionStatus"
        else:
            if exit_code_str == "0":
                action["actionStatus"] = "http://schema.org/CompletedActionStatus"
            else:
                action["actionStatus"] = "http://schema.org/FailedActionStatus"

    # Description: summary text
    wf_name = Path(run_request.workflow_url).name or run_request.workflow_url
    action["description"] = f"Executed {wf_name} using {run_request.workflow_engine}"

    # Error from stderr (failure only)
    if action.get("actionStatus") == "http://schema.org/FailedActionStatus":
        stderr_content = read_run_dir_file(run_dir, "stderr", raw=True)
        if stderr_content:
            lines = stderr_content.strip().splitlines()
            tail = lines[-_STDERR_TAIL_LINES:] if len(lines) > _STDERR_TAIL_LINES else lines
            action["error"] = "\n".join(tail)

    # Agent
    agent = add_agent(crate, run_dir)
    if agent is not None:
        action.append_to("agent", agent, compact=True)

    # Container image
    container = add_container_image(crate, run_dir)
    if container is not None:
        action.append_to("containerImage", container, compact=True)

    crate.add(action)

    # Inputs
    add_input_parameters(crate, wf, action, run_dir, run_request)
    add_input_file_entities(crate, wf, action, run_dir, run_request)

    # Outputs
    add_output_file_entities(crate, wf, action, run_dir)

    # Logs
    add_log_file_entities(crate, action, run_dir)

    # MultiQC stats
    add_multiqc_stats(crate, run_dir, action)

    # Ensure result and object are always arrays (even for failed runs with no outputs/inputs)
    if action.get("result") is None:
        action["result"] = []
    if action.get("object") is None:
        action["object"] = []

    return action


# === File metadata ===


def populate_file_metadata(
    file_ins: File, file_path: Path, include_content: bool = True, include_force: bool = False
) -> None:
    """Add file metadata such as ``contentSize`` and ``sha256`` to the file instance.

    The instance itself is updated in place.
    """
    if not file_path.is_file():
        return

    try:
        stat_result = file_path.stat()
    except OSError:
        return
    file_ins["contentSize"] = stat_result.st_size
    file_ins["dateModified"] = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc).isoformat()

    with contextlib.suppress(OSError, UnicodeDecodeError):
        file_ins["lineCount"] = count_lines(file_path)

    with contextlib.suppress(OSError):
        file_ins["sha256"] = compute_sha256(file_path)

    if include_content and (include_force or file_ins["contentSize"] < 10 * 1024):
        with contextlib.suppress(OSError, UnicodeDecodeError):
            file_ins["text"] = file_path.read_text()

    try:
        mime_type = magic.from_file(str(file_path), mime=True)
    except (OSError, ValueError):
        mime_type = "application/octet-stream"
    if mime_type.startswith("inode/"):
        mime_type = "application/octet-stream"
    file_ins["encodingFormat"] = mime_type

    edam = inspect_edam_format(file_path)
    if edam is not None:
        edam_entity = ContextEntity(
            file_ins.crate,
            edam.url,
            properties={"@type": "Thing", "name": edam.name},
        )
        file_ins.crate.add(edam_entity)
        file_ins.append_to("encodingFormat", edam_entity)


# === Bioinformatics extensions ===


def add_multiqc_stats(crate: ROCrate, run_dir: Path, create_action_ins: ContextEntity) -> None:
    """Run multiqc in Docker and add multiqc stats to the crate.

    Requires Docker daemon to be running (``shutil.which`` only checks the
    binary exists on PATH, not that the daemon is up).
    """
    if shutil.which("docker") is None:
        return

    logger = logging.getLogger("sapporo")
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{run_dir}:/work",
        "-w",
        "/work",
        "quay.io/biocontainers/multiqc:1.33--pyhdfd78af_0",
        "multiqc",
        "--data-format",
        "json",
        "--quiet",
        "--no-report",
        "/work",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        logger.warning("MultiQC Docker command failed (rc=%d): %s", proc.returncode, proc.stderr.decode()[:500])

    multiqc_data_dir = run_dir / "multiqc_data"
    multiqc_stats = run_dir / RUN_DIR_STRUCTURE["multiqc_stats"]

    if multiqc_data_dir.exists() and multiqc_data_dir.joinpath("multiqc_general_stats.json").exists():
        shutil.move(str(multiqc_data_dir / "multiqc_general_stats.json"), str(multiqc_stats))
        shutil.rmtree(str(multiqc_data_dir))

    if not multiqc_stats.exists():
        return

    file_ins = File(
        crate,
        multiqc_stats,
        multiqc_stats.relative_to(run_dir),
        properties={"name": "MultiQC stats"},
    )
    populate_file_metadata(file_ins, multiqc_stats, include_content=True, include_force=True)
    create_action_ins.append_to("multiqcStats", file_ins)
    crate.add(file_ins)


def add_file_stats(crate: ROCrate, file_ins: File) -> None:
    """Add file statistics using Docker-based bioinformatics tools.

    Requires Docker daemon to be running (``shutil.which`` only checks the
    binary exists on PATH, not that the daemon is up).
    """
    if shutil.which("docker") is None:
        return

    formats = get_norm_value(file_ins, "encodingFormat")
    for format_ in formats:
        if format_ in ("http://edamontology.org/format_2572", "http://edamontology.org/format_2573"):
            add_samtools_stats(crate, file_ins)
        elif format_ == "http://edamontology.org/format_3016":
            add_vcftools_stats(crate, file_ins)


def add_samtools_stats(crate: ROCrate, file_ins: File) -> None:
    """Add samtools flagstats statistics to the file instance."""
    logger = logging.getLogger("sapporo")
    source = file_ins.source
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{source}:/work/{source.name}",
        "-w",
        "/work",
        "quay.io/biocontainers/samtools:1.23--h96c455f_0",
        "samtools",
        "flagstats",
        "--output-fmt",
        "json",
        source.name,
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        logger.warning(
            "samtools Docker command failed for %s (rc=%d): %s",
            file_ins.id,
            proc.returncode,
            proc.stderr.decode()[:500],
        )
        return
    try:
        stats = json.loads(proc.stdout)
        total = stats["QC-passed reads"]["total"]
        mapped = stats["QC-passed reads"]["mapped"]
        unmapped = total - mapped
        duplicate = stats["QC-passed reads"]["duplicates"]
        properties: dict[str, Any] = {
            "@type": ["FileStats"],
            "totalReads": total,
            "mappedReads": mapped,
            "unmappedReads": unmapped,
            "duplicateReads": duplicate,
        }
        if total > 0:
            properties["mappedRate"] = mapped / total
            properties["unmappedRate"] = unmapped / total
            properties["duplicateRate"] = duplicate / total
        else:
            properties["mappedRate"] = 0.0
            properties["unmappedRate"] = 0.0
            properties["duplicateRate"] = 0.0
        stats_ins = ContextEntity(crate, properties=properties)
        stats_ins.append_to(
            "generatedBy", find_or_generate_software_ins(crate, "samtools", "1.23--h96c455f_0"), compact=True
        )
        file_ins.append_to("stats", stats_ins, compact=True)
        crate.add(stats_ins)
    except json.JSONDecodeError:
        logging.getLogger("sapporo").warning("Failed to parse samtools output for %s", file_ins.id)
        return


def add_vcftools_stats(crate: ROCrate, file_ins: File) -> None:
    """Add vcftools statistics to the file instance."""
    logger = logging.getLogger("sapporo")
    source = file_ins.source
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{source}:/work/{source.name}",
        "-w",
        "/work",
        "quay.io/biocontainers/vcftools:0.1.17--pl5321h077b44d_0",
        "vcf-stats",
        source.name,
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        logger.warning(
            "vcftools Docker command failed for %s (rc=%d): %s",
            file_ins.id,
            proc.returncode,
            proc.stderr.decode()[:500],
        )
        return
    try:
        stdout_str = proc.stdout.decode()

        def _extract_int(text: str, key: str) -> int:
            match = re.search(rf"'{key}'\s*=>\s*(\d+)", text)
            return int(match.group(1)) if match else 0

        stats_ins = ContextEntity(
            crate,
            properties={
                "@type": ["FileStats"],
                "variantCount": _extract_int(stdout_str, "count"),
                "snpsCount": _extract_int(stdout_str, "snp_count"),
                "indelsCount": _extract_int(stdout_str, "indel_count"),
            },
        )
        stats_ins.append_to(
            "generatedBy", find_or_generate_software_ins(crate, "vcftools", "0.1.17--pl5321h077b44d_0"), compact=True
        )
        file_ins.append_to("stats", stats_ins, compact=True)
        crate.add(stats_ins)
    except (UnicodeDecodeError, ValueError):
        logging.getLogger("sapporo").warning("Failed to parse vcftools output for %s", file_ins.id)
        return


_ENGINE_URL_MAP: dict[str, str] = {
    "cwltool": "https://github.com/common-workflow-language/cwltool",
    "nextflow": "https://www.nextflow.io",
    "toil": "https://toil.ucsc.edu",
    "cromwell": "https://github.com/broadinstitute/cromwell",
    "snakemake": "https://snakemake.github.io",
    "ep3": "https://github.com/tom-tan/ep3",
    "streamflow": "https://github.com/alpha-unito/streamflow",
    "samtools": "https://github.com/samtools/samtools",
    "vcftools": "https://github.com/vcftools/vcftools",
    "sapporo": "https://github.com/sapporo-wes/sapporo-service",
}


def find_or_generate_software_ins(crate: ROCrate, name: str, version: str) -> SoftwareApplication:
    for entity in crate.get_entities():
        if isinstance(entity, SoftwareApplication) and entity["name"] == name:
            return entity

    url = _ENGINE_URL_MAP.get(name.lower())
    identifier = url or f"#{name}"
    props: dict[str, Any] = {"name": name, "softwareVersion": version}
    if url is not None:
        props["url"] = url
    software_ins = SoftwareApplication(crate, identifier=identifier, properties=props)
    crate.add(software_ins)

    return software_ins


# === README ===


def add_readme_entity(crate: ROCrate, run_dir: Path, run_id: str) -> None:
    """Add a README.md File entity to the RO-Crate."""
    readme_path = run_dir / "README.md"
    file_ins = File(
        crate,
        readme_path,
        "README.md",
        properties={
            "name": "README",
            "about": {"@id": "./"},
            "encodingFormat": "text/markdown",
        },
    )
    crate.add(file_ins)


# === Entry points ===


def generate_ro_crate_metadata(run_dir: Path) -> dict[str, Any]:
    """Generate RO-Crate metadata as a JSON-LD dict (for testing)."""
    crate = create_base_crate()

    raw_run_request = read_run_dir_file(run_dir, "run_request")
    if not isinstance(raw_run_request, dict):
        msg = f"run_request.json is missing or invalid in {run_dir} (got {type(raw_run_request).__name__})"
        raise TypeError(msg)
    run_request = load_run_request(raw_run_request)
    runtime_info = read_run_dir_file(run_dir, "runtime_info")
    run_id = runtime_info["run_id"] if isinstance(runtime_info, dict) and "run_id" in runtime_info else run_dir.name

    # Root Data Entity: REQUIRED properties
    crate.name = f"Sapporo WES run {run_id}"
    crate.description = f"RO-Crate for workflow run {run_id} executed by Sapporo WES"

    # License: textual note on Root Data Entity (the crate contains user files
    # whose licensing is unknown to sapporo). CC0 is set separately on the
    # Metadata Descriptor in create_base_crate().
    crate.root_dataset["license"] = (
        "The RO-Crate metadata was generated by sapporo-service. "
        "Licensing of individual workflow files, input data, and output data "
        "is determined by their respective owners."
    )

    # Publisher: Sapporo Organization (generated and serves this crate)
    sapporo_org = ContextEntity(
        crate,
        "https://github.com/sapporo-wes",
        properties={
            "@type": "Organization",
            "name": "Sapporo WES Project",
            "url": "https://github.com/sapporo-wes",
        },
    )
    crate.add(sapporo_org)
    crate.root_dataset["publisher"] = sapporo_org

    # datePublished on Root Data Entity
    crate.root_dataset["datePublished"] = datetime.now(timezone.utc).isoformat()

    wf = add_workflow_entity(crate, run_dir, run_request)
    engine_ins, sapporo_ins = add_software_entities(crate, run_request, run_dir)
    action = add_create_action(crate, wf, run_dir, run_request, run_id)

    # executedBy: link CreateAction to SoftwareApplication entities
    if engine_ins is not None:
        action.append_to("executedBy", engine_ins, compact=True)
    if sapporo_ins is not None:
        action.append_to("executedBy", sapporo_ins, compact=True)

    add_readme_entity(crate, run_dir, run_id)

    result: dict[str, Any] = crate.metadata.generate()

    return result


def generate_ro_crate(inputted_run_dir: str) -> None:
    """Generate an RO-Crate metadata file for the given run directory.

    This function is the entry point of this ``ro_crate.py`` module.
    Executed in run.sh as::

        sapporo-cli generate-ro-crate ${run_dir}

    """
    run_dir = Path(inputted_run_dir).resolve(strict=True)
    if not run_dir.is_dir():
        msg = f"{run_dir} is not a directory."
        raise NotADirectoryError(msg)

    runtime_info = read_run_dir_file(run_dir, "runtime_info")
    run_id = runtime_info["run_id"] if isinstance(runtime_info, dict) and "run_id" in runtime_info else run_dir.name
    readme_path = run_dir / "README.md"
    readme_path.write_text(
        f"# Sapporo WES run {run_id}\n\nRO-Crate for workflow run `{run_id}` executed by Sapporo WES.\n",
        encoding="utf-8",
    )

    jsonld = generate_ro_crate_metadata(run_dir)
    with run_dir.joinpath("ro-crate-metadata.json").open(mode="w", encoding="utf-8") as f:
        json.dump(jsonld, f, indent=2, sort_keys=True)
