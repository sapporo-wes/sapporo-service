#!/usr/bin/env python3
# coding: utf-8
import gc
import hashlib
import json
import os
import platform
import shlex
import shutil
import stat
import subprocess
import urllib
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict, cast
from urllib.parse import urlsplit

import magic
import psutil
import yaml
from rocrate.model.computationalworkflow import ComputationalWorkflow
from rocrate.model.computerlanguage import ComputerLanguage
from rocrate.model.computerlanguage import get_lang as ro_crate_get_lang
from rocrate.model.contextentity import ContextEntity
from rocrate.model.data_entity import DataEntity
from rocrate.model.dataset import Dataset
from rocrate.model.file import File
from rocrate.model.metadata import WORKFLOW_PROFILE, Metadata
from rocrate.model.root_dataset import RootDataset
from rocrate.model.softwareapplication import SoftwareApplication
from rocrate.model.testdefinition import TestDefinition
from rocrate.model.testinstance import TestInstance
from rocrate.model.testservice import TestService
from rocrate.model.testsuite import TestSuite
from rocrate.rocrate import ROCrate
from rocrate.utils import get_norm_value

from sapporo.const import RUN_DIR_STRUCTURE, RUN_DIR_STRUCTURE_KEYS
from sapporo.model import AttachedFile, RunRequest, ServiceInfo

TERM_FNAME = "wes-ro-terms.csv"
TERM_PATH = Path(__file__).parent.joinpath(TERM_FNAME)
TERM_URL_BASE = f"https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/sapporo/{TERM_FNAME}"
SAPPORO_EXTRA_TERMS: Dict[str, str] = {}
with TERM_PATH.open(mode="r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("term"):
            continue
        term = line.strip().split(",")[0]
        SAPPORO_EXTRA_TERMS[term] = f"{TERM_URL_BASE}#{term}"

class YevisAuthor(TypedDict):
    github_account: str
    name: str
    affiliation: str
    orcid: Optional[str]

class YevisLanguage(TypedDict):
    type: str
    version: str

class YevisFile(TypedDict):
    url: str
    target: str
    type: Literal["primary", "secondary"]

class YevisTestFile(TypedDict):
    url: str
    target: str
    type: Literal["wf_params", "wf_engine_params", "other"]

class YevisTest(TypedDict):
    id: str
    files: List[YevisTestFile]

class YevisWorkflow(TypedDict):
    name: str
    readme: str
    language: YevisLanguage
    files: List[YevisFile]
    testing: List[YevisTest]

class YevisMetadata(TypedDict):
    id: str
    version: str
    license: str
    authors: List[YevisAuthor]
    workflow: YevisWorkflow

class EDAM(TypedDict):
    url: str
    name: str

EDAM_MAPPING: Dict[str, EDAM] = {
    ".bam": {
        "url": "http://edamontology.org/format_2572",
        "name": "BAM format, the binary, BGZF-formatted compressed version of SAM format for alignment of nucleotide sequences (e.g. sequencing reads) to (a) reference sequence(s). May contain base-call and alignment qualities and other data.",
    },
    ".bb": {
        "url": "http://edamontology.org/format_3004",
        "name": "bigBed format for large sequence annotation tracks, similar to textual BED format.",
    },
    ".bed": {
        "url": "http://edamontology.org/format_3003",
        "name": "Browser Extensible Data (BED) format of sequence annotation track, typically to be displayed in a genome browser.",
    },
    ".bw": {
        "url": "http://edamontology.org/format_3006",
        "name": "bigWig format for large sequence annotation tracks that consist of a value for each sequence position. Similar to textual WIG format.",
    },
    ".fa": {
        "url": "http://edamontology.org/format_1929",
        "name": "FASTA format including NCBI-style IDs.",
    },
    ".fasta": {
        "url": "http://edamontology.org/format_1929",
        "name": "FASTA format including NCBI-style IDs.",
    },
    ".fastq": {
        "url": "http://edamontology.org/format_1930",
        "name": "FASTQ short read format ignoring quality scores.",
    },
    ".fastq.gz": {
        "url": "http://edamontology.org/format_1930",
        "name": "FASTQ short read format ignoring quality scores.",
    },
    ".fq": {
        "url": "http://edamontology.org/format_1930",
        "name": "FASTQ short read format ignoring quality scores.",
    },
    ".fq.gz": {
        "url": "http://edamontology.org/format_1930",
        "name": "FASTQ short read format ignoring quality scores.",
    },
    ".gtf": {
        "url": "http://edamontology.org/format_2306",
        "name": "Gene Transfer Format (GTF), a restricted version of GFF.",
    },
    ".gff": {
        "url": "http://edamontology.org/format_1975",
        "name": "Generic Feature Format version 3 (GFF3) of sequence features.",
    },
    ".sam": {
        "url": "http://edamontology.org/format_2573",
        "name": "Sequence Alignment/Map (SAM) format for alignment of nucleotide sequences (e.g. sequencing reads) to (a) reference sequence(s). May contain base-call and alignment qualities and other data.",
    },
    ".vcf": {
        "url": "http://edamontology.org/format_3016",
        "name": "Variant Call Format (VCF) for sequence variation (indels, polymorphisms, structural variation).",
    },
    ".vcf.gz": {
        "url": "http://edamontology.org/format_3016",
        "name": "Variant Call Format (VCF) for sequence variation (indels, polymorphisms, structural variation).",
    },
    ".wig": {
        "url": "http://edamontology.org/format_3005",
        "name": "Wiggle format (WIG) of a sequence annotation track that consists of a value for each sequence position. Typically to be displayed in a genome browser.",
    },
}

# === functions ===

def generate_ro_crate(inputted_run_dir: str) -> None:
    """\
    Called in run.sh
    """
    run_dir: Path = Path(inputted_run_dir).resolve(strict=True)
    if not run_dir.is_dir():
        raise NotADirectoryError(f"{run_dir} is not a directory.")

    crate = ROCrate(init=False, gen_preview=False)

    run_request: RunRequest = read_file(run_dir, "run_request")
    yevis_metadata: Optional[YevisMetadata] = read_file(run_dir, "yevis_metadata")
    run_id = run_dir.name

    add_crate_metadata(crate)
    add_extra_terms(crate)
    add_workflow(crate, run_dir, run_request, yevis_metadata)
    add_workflow_attachment(crate, run_dir, run_request, yevis_metadata)
    add_workflow_run(crate, run_dir, run_id)
    add_workflow_execution_service(crate)

    crate.write(run_dir)

def read_file(run_dir: Path, file_type: RUN_DIR_STRUCTURE_KEYS, one_line: bool = False, raw: bool = False) -> Any:
    if "dir" in file_type:
        return None
    file_path = run_dir.joinpath(RUN_DIR_STRUCTURE[file_type])
    if file_path.exists() is False:
        return None
    if file_path.is_file() is False:
        return None
    with file_path.open(mode="r", encoding="utf-8") as f:
        if one_line:
            return f.readline().strip()
        if raw:
            return f.read()
        try:
            return yaml.load(f, Loader=yaml.SafeLoader)
        except Exception:
            return f.read()

def add_crate_metadata(crate: ROCrate) -> None:
    # @id: ro-crate-metadata.json
    profiles = set(_.rstrip("/") for _ in get_norm_value(crate.metadata, "conformsTo"))
    profiles.add(WORKFLOW_PROFILE)
    crate.metadata["conformsTo"] = [{"@id": _} for _ in sorted(profiles)]

    # @id: ./
    profiles.add("https://w3id.org/ro/wfrun/workflow/0.1")
    crate.root_dataset["conformsTo"] = [{"@id": _} for _ in sorted(profiles)]

def add_extra_terms(crate: ROCrate) -> None:
    crate.metadata.extra_terms.update(SAPPORO_EXTRA_TERMS)

def add_workflow(crate: ROCrate, run_dir: Path, run_request: RunRequest, yevis_meta: Optional[YevisMetadata]) -> None:
    """\
    Modified from crate.add_workflow()

    RunRequest:
      - wf_url: Remote location, or local file path attached as workflow_attachment and downloaded to exe_dir
    """
    wf_url = cast(str, run_request["workflow_url"])
    wf_url_parts = urlsplit(wf_url)
    if wf_url_parts.scheme == "http" or wf_url_parts.scheme == "https":
        wf_ins = ComputationalWorkflow(crate, wf_url)
    else:
        wf_file_path = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"], wf_url).resolve(strict=True)
        wf_ins = ComputationalWorkflow(crate, wf_file_path, wf_file_path.relative_to(run_dir))
        append_exe_dir_dataset(crate, wf_ins)

    crate.add(wf_ins)

    if run_request["workflow_name"] is not None:
        wf_ins["name"] = run_request["workflow_name"]

    wf_ins.lang = generate_wf_lang(crate, run_request)

    crate.mainEntity = wf_ins

    if yevis_meta is not None:
        wf_ins["yevisId"] = yevis_meta["id"]
        wf_ins["version"] = yevis_meta["version"]
        wf_ins["name"] = yevis_meta["workflow"]["name"]
        description_ins = ContextEntity(crate, yevis_meta["workflow"]["readme"], properties={
            "@type": ["WebPage"],
            "name": "README.md",
        })
        crate.add(description_ins)
        wf_ins["description"] = description_ins

def update_local_file_stat(crate: ROCrate, file_ins: File, file_path: Path, include_content: bool = True) -> None:
    if file_path.is_file() is False:
        return
    if file_path.exists() is False:
        return

    # From file stat
    stat_result = file_path.stat()

    # https://schema.org/MediaObject
    file_ins["contentSize"] = stat_result.st_size
    file_ins["dateModified"] = datetime.fromtimestamp(stat_result.st_mtime).isoformat()

    # add file line count
    try:
        file_ins["lineCount"] = count_lines(file_path)
    except UnicodeDecodeError:
        pass

    # checksum using sha512 (https://www.researchobject.org/ro-crate/1.1/appendix/implementation-notes.html#combining-with-other-packaging-schemes)
    file_ins["sha512"] = generate_sha512(file_path)


    if include_content:
        # under 10kb, attach as text
        if file_ins["contentSize"] < 10 * 1024:
            try:
                file_ins["text"] = file_path.read_text()
            except UnicodeDecodeError:
                pass

    edam = inspect_edam_format(file_path)
    if edam is not None:
        file_ins.append_to("encodingFormat", edam["url"], compact=True)
    else:
        # https://pypi.org/project/python-magic/
        file_ins["encodingFormat"] = magic.from_file(file_path, mime=True)

def append_exe_dir_dataset(crate: ROCrate, ins: DataEntity) -> None:
    for entity in crate.get_entities():
        if isinstance(entity, Dataset):
            if str(entity["@id"]) == f"{RUN_DIR_STRUCTURE['exe_dir']}/":
                entity.append_to("hasPart", ins, compact=True)

def count_lines(file_path: Path) -> int:
    block_size = 65536
    count = 0
    with file_path.open("r") as f:
        while True:
            buffer = f.read(block_size)
            if not buffer:
                break
            count += buffer.count("\n")

    del buffer
    gc.collect()

    return count

def generate_sha512(file_path: Path) -> str:
    block_size = 65536
    sha512 = hashlib.sha512()
    with file_path.open("rb") as f:
        while True:
            buffer = f.read(block_size)
            if not buffer:
                break
            sha512.update(buffer)

    hash_ = str(sha512.hexdigest())
    del sha512
    gc.collect()

    return hash_

def inspect_edam_format(file_path: Path) -> Optional[EDAM]:
    """\
    TODO: use tataki (https://github.com/suecharo/tataki)
    """
    for ext, edam in EDAM_MAPPING.items():
        if file_path.name.endswith(ext):
            return edam

    return None

def generate_wf_lang(crate: ROCrate, run_request: RunRequest) -> ComputerLanguage:
    """\
    wf_type: "CWL", "WDL", "NFL", "SMK" or others
    wf_type_version: str
    """
    wf_type = cast(str, run_request["workflow_type"])
    wf_type_version = cast(str, run_request["workflow_type_version"])

    lang_type_for_ro_crate = wf_type
    if wf_type.lower() == "nfl":
        lang_type_for_ro_crate = "nextflow"
    elif wf_type.lower() == "smk":
        lang_type_for_ro_crate = "snakemake"
    try:
        lang_ins = ro_crate_get_lang(crate, lang_type_for_ro_crate, wf_type_version)
        for filed in ["identifier", "url"]:
            id_ = get_norm_value(lang_ins, filed)[0]
            cxt = ContextEntity(crate, id_, properties={
                "@type": ["WebPage"],
            })
            crate.add(cxt)
            # lang_ins.append_to(filed, cxt) # bug of ro_crate_py
    except ValueError as e:
        if "Unknown language" in str(e):
            # case: WDL or others
            if wf_type.lower() == "wdl":
                id_ = "https://openwdl.org"
                lang_ins = ComputerLanguage(
                    crate,
                    id_,
                    properties={
                        "name": "Workflow Description Language",
                        "alternateName": "WDL",
                        "version": wf_type_version,
                    })
                ctx = ContextEntity(crate, id_, properties={
                    "@type": ["WebPage"],
                })
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
                    })
        else:
            raise e

    crate.add(lang_ins)

    return lang_ins

def add_workflow_attachment(crate: ROCrate, run_dir: Path, run_request: RunRequest,
                            yevis_meta: Optional[YevisMetadata]) -> None:
    """\
    If no Yevis (Sapporo only): All workflow attachments are treated as workflow inputs.
    If with Yevis: Workflow attachments are treated as workflow inputs, but test files are added to TestDefinition.

    workflow_attachment are placed in exe_dir (downloaded)
    """
    main_wf_id = crate.mainEntity["@id"]

    if yevis_meta is None:
        secondary_files: List[str] = []
    else:
        secondary_files = [file["target"] for file in yevis_meta["workflow"]["files"] if file["type"] == "secondary"]

    wf_attachment = cast(str, run_request["workflow_attachment"])  # encoded json string
    wf_attachment_obj: List[AttachedFile] = json.loads(wf_attachment)
    for item in wf_attachment_obj:
        if yevis_meta is not None:
            if item["file_name"] not in secondary_files:
                continue

        source = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"], item["file_name"])
        dest = source.relative_to(run_dir)
        if str(dest) == str(main_wf_id):
            continue
        type_list = ["File", "FormalParameter", "WorkflowAttachment"]
        if "script" in magic.from_file(source):
            type_list.append("SoftwareSourceCode")

        if yevis_meta is None:
            url = item["file_url"]
        else:
            file = [f for f in yevis_meta["workflow"]["files"] if f["target"] == item["file_name"]][0]
            url = file["url"]

        file_ins = File(crate, source, dest, properties={
            "@type": type_list,
            "url": url,
        })
        update_local_file_stat(crate, file_ins, source, include_content=False)
        append_exe_dir_dataset(crate, file_ins)
        crate.mainEntity.append_to("attachment", file_ins, compact=True)
        crate.add(file_ins)

def add_workflow_run(crate: ROCrate, run_dir: Path, run_id: str) -> None:
    create_action_ins = generate_create_action(crate, run_dir, run_id)
    wf_ins = crate.mainEntity
    create_action_ins.append_to("instrument", wf_ins, compact=True)

def generate_create_action(crate: ROCrate, run_dir: Path, run_id: str) -> ContextEntity:
    create_action_ins = ContextEntity(crate, identifier=run_id, properties={
        "@type": "CreateAction",
        "name": "Sapporo workflow run " + run_id,
    })
    crate.add(create_action_ins)

    # Add one-line text files
    one_line_files: List[Tuple[RUN_DIR_STRUCTURE_KEYS, str]] = [
        ("start_time", "startTime"),
        ("end_time", "endTime"),
        ("exit_code", "exitCode"),
        # ("pid", "pid"),
        ("state", "state"),
    ]
    for key, field_key in one_line_files:
        content = read_file(run_dir, key, one_line=True)
        if content is None:
            continue
        if key == "pid" or key == "exit_code":
            create_action_ins[field_key] = int(content)
        else:
            create_action_ins[field_key] = content

    # Add log files
    log_files: List[Tuple[RUN_DIR_STRUCTURE_KEYS, str]] = [
        ("stdout", "Sapporo stdout"),
        ("stderr", "Sapporo stderr"),
        ("task_logs", "Sapporo task logs"),
    ]
    for key, name in log_files:
        source = run_dir.joinpath(RUN_DIR_STRUCTURE[key])
        if source.exists() is False:
            continue
        dest = source.relative_to(run_dir)
        file_ins = File(crate, source, dest, properties={
            "name": name,
        })
        update_local_file_stat(crate, file_ins, source)
        create_action_ins.append_to("subjectOf", file_ins)
        crate.mainEntity.append_to("output", file_ins)
        crate.add(file_ins)

    # Add output files
    outputs: Optional[List[AttachedFile]] = read_file(run_dir, "outputs")
    for source in run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"]).glob("**/*"):
        if source.is_dir():
            continue
        source = source.resolve(strict=True)
        dest = source.relative_to(run_dir)
        file_ins = File(crate, source, dest, properties={
            "@type": "File",
        })
        update_local_file_stat(crate, file_ins, source)

        if outputs is not None:
            # Include the URL of Sapporo's download feature
            output_dir_dest = source.relative_to(run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"]))
            for output in outputs:
                if str(output["file_name"]) == str(output_dir_dest):
                    file_ins["url"] = output["file_url"]

        add_file_stats(crate, file_ins)

        append_outputs_dir_dataset(crate, file_ins)
        crate.mainEntity.append_to("output", file_ins)
        create_action_ins.append_to("result", file_ins)
        crate.add(file_ins)

    # Add intermediate files
    create_action_ins["object"] = []
    already_added_ids = extract_exe_dir_file_ids(crate)
    for source in run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"]).glob("**/*"):
        if source.is_dir():
            continue
        source = source.resolve(strict=True)
        dest = source.relative_to(run_dir)
        if str(dest) in already_added_ids:
            continue
        file_ins = File(crate, source, dest, properties={
            "@type": "File",
        })
        update_local_file_stat(crate, file_ins, source, include_content=False)
        append_exe_dir_dataset(crate, file_ins)
        create_action_ins.append_to("object", file_ins)
        crate.mainEntity.append_to("input", file_ins)
        crate.add(file_ins)

    crate.root_dataset.append_to("mentions", create_action_ins, compact=True)

    return create_action_ins

def add_file_stats(crate: ROCrate, file_ins: File) -> None:
    """\
    see "format" field of file_ins

    ".bam": "http://edamontology.org/format_2572"
    ".sam": "http://edamontology.org/format_2573",
      -> quay.io/biocontainers/samtools:1.15.1--h1170115_0
    ".vcf": "http://edamontology.org/format_3016",
      -> quay.io/biocontainers/vcftools:0.1.16--pl5321h9a82719_6
    """
    # TODO: use docker or local command?
    if shutil.which("docker") is None:
        return

    formats = get_norm_value(file_ins, "format")
    for format_ in formats:
        if format_ == "http://edamontology.org/format_2572" or format_ == "http://edamontology.org/format_2573":
            # bam or sam
            add_samtools_stats(crate, file_ins)
        elif format_ == "http://edamontology.org/format_3016":
            # vcf
            add_vcftools_stats(crate, file_ins)

def append_outputs_dir_dataset(crate: ROCrate, ins: DataEntity) -> None:
    for entity in crate.get_entities():
        if isinstance(entity, Dataset):
            if str(entity["@id"]) == f"{RUN_DIR_STRUCTURE['outputs_dir']}/":
                entity.append_to("hasPart", ins, compact=True)


def extract_exe_dir_file_ids(crate: ROCrate) -> List[str]:
    for entity in crate.get_entities():
        if isinstance(entity, Dataset):
            if str(entity["@id"]) == f"{RUN_DIR_STRUCTURE['exe_dir']}/":
                return cast(List[str], get_norm_value(entity, "hasPart"))
    return []

def add_workflow_execution_service(crate: ROCrate) -> None:
    crate

# === main ===

if __name__ == "__main__":
    import sys
    inputted_dir = Path(sys.argv[1]).resolve(strict=True)
    generate_ro_crate(str(inputted_dir))
