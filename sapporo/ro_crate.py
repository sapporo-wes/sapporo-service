#!/usr/bin/env python3
# coding: utf-8
import contextlib
import gc
import hashlib
import io
import json
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import magic
import multiqc
from fastapi import UploadFile
from pydantic import BaseModel, TypeAdapter
from rocrate.model.computationalworkflow import ComputationalWorkflow
from rocrate.model.computerlanguage import ComputerLanguage
from rocrate.model.computerlanguage import get_lang as ro_crate_get_lang
from rocrate.model.contextentity import ContextEntity
from rocrate.model.creativework import CreativeWork
from rocrate.model.data_entity import DataEntity
from rocrate.model.dataset import Dataset
from rocrate.model.file import File
from rocrate.model.metadata import WORKFLOW_PROFILE
from rocrate.model.softwareapplication import SoftwareApplication
from rocrate.rocrate import ROCrate
from rocrate.utils import get_norm_value

from sapporo.config import RUN_DIR_STRUCTURE, RunDirStructureKeys
from sapporo.schemas import FileObject, RunRequestForm

SAPPORO_EXTRA_CONTEXT = "https://w3id.org/ro/terms/sapporo"
WF_RUN_CRATE_CONTEXT = "https://w3id.org/ro/terms/workflow-run"


class EDAM(BaseModel):
    url: str
    name: str


EDAM_MAPPING: Dict[str, EDAM] = {
    ".bam": EDAM(**{
        "url": "http://edamontology.org/format_2572",
        "name": "BAM format, the binary, BGZF-formatted compressed version of SAM format for alignment of nucleotide sequences (e.g. sequencing reads) to (a) reference sequence(s). May contain base-call and alignment qualities and other data.",
    }),
    ".bb": EDAM(**{
        "url": "http://edamontology.org/format_3004",
        "name": "bigBed format for large sequence annotation tracks, similar to textual BED format.",
    }),
    ".bed": EDAM(**{
        "url": "http://edamontology.org/format_3003",
        "name": "Browser Extensible Data (BED) format of sequence annotation track, typically to be displayed in a genome browser.",
    }),
    ".bw": EDAM(**{
        "url": "http://edamontology.org/format_3006",
        "name": "bigWig format for large sequence annotation tracks that consist of a value for each sequence position. Similar to textual WIG format.",
    }),
    ".fa": EDAM(**{
        "url": "http://edamontology.org/format_1929",
        "name": "FASTA format including NCBI-style IDs.",
    }),
    ".fasta": EDAM(**{
        "url": "http://edamontology.org/format_1929",
        "name": "FASTA format including NCBI-style IDs.",
    }),
    ".fastq": EDAM(**{
        "url": "http://edamontology.org/format_1930",
        "name": "FASTQ short read format ignoring quality scores.",
    }),
    ".fastq.gz": EDAM(**{
        "url": "http://edamontology.org/format_1930",
        "name": "FASTQ short read format ignoring quality scores.",
    }),
    ".fq": EDAM(**{
        "url": "http://edamontology.org/format_1930",
        "name": "FASTQ short read format ignoring quality scores.",
    }),
    ".fq.gz": EDAM(**{
        "url": "http://edamontology.org/format_1930",
        "name": "FASTQ short read format ignoring quality scores.",
    }),
    ".gtf": EDAM(**{
        "url": "http://edamontology.org/format_2306",
        "name": "Gene Transfer Format (GTF), a restricted version of GFF.",
    }),
    ".gff": EDAM(**{
        "url": "http://edamontology.org/format_1975",
        "name": "Generic Feature Format version 3 (GFF3) of sequence features.",
    }),
    ".sam": EDAM(**{
        "url": "http://edamontology.org/format_2573",
        "name": "Sequence Alignment/Map (SAM) format for alignment of nucleotide sequences (e.g. sequencing reads) to (a) reference sequence(s). May contain base-call and alignment qualities and other data.",
    }),
    ".vcf": EDAM(**{
        "url": "http://edamontology.org/format_3016",
        "name": "Variant Call Format (VCF) for sequence variation (indels, polymorphisms, structural variation).",
    }),
    ".vcf.gz": EDAM(**{
        "url": "http://edamontology.org/format_3016",
        "name": "Variant Call Format (VCF) for sequence variation (indels, polymorphisms, structural variation).",
    }),
    ".wig": EDAM(**{
        "url": "http://edamontology.org/format_3005",
        "name": "Wiggle format (WIG) of a sequence annotation track that consists of a value for each sequence position. Typically to be displayed in a genome browser.",
    }),
}


# === functions ===


def generate_ro_crate(inputted_run_dir: str) -> None:
    """\
    This function can be an entry point of this `ro_crate.py` module
    Executed in run.sh as:

    `python3 -c "from sapporo.ro_crate import generate_ro_crate; generate_ro_crate('${run_dir}')" || echo "{}" >"${run_dir}/ro-crate-metadata.json" || true`

    This `run_dir` is the directory where the run is executed, and the absolute path is passed.
    Also, as a debug, if you execute `python3 ro_crate.py <run_dir>`, `<run_dir>/ro-crate-metadata.json` will be generated.
    """
    run_dir = Path(inputted_run_dir).resolve(strict=True)
    if not run_dir.is_dir():
        raise NotADirectoryError(f"{run_dir} is not a directory.")

    crate = ROCrate(init=False, gen_preview=False)

    run_request = load_run_request(read_file(run_dir, "run_request"))
    run_id = run_dir.name

    add_crate_metadata(crate)
    add_run_crate_profile(crate)
    add_workflow(crate, run_dir, run_request)
    add_workflow_run(crate, run_dir, run_request, run_id)

    jsonld = crate.metadata.generate()
    if isinstance(jsonld["@context"], str):
        jsonld["@context"] = [jsonld["@context"]]
    jsonld["@context"].append(SAPPORO_EXTRA_CONTEXT)
    jsonld["@context"].append(WF_RUN_CRATE_CONTEXT)
    with run_dir.joinpath(crate.metadata.BASENAME).open(mode="w", encoding="utf-8") as f:
        json.dump(jsonld, f, indent=2, sort_keys=True)


def read_file(
        run_dir: Path,
        key: RunDirStructureKeys,
        one_line: bool = False,
        raw: bool = False
) -> Any:
    """\
    Read a file in run_dir.
    There is a function with the same name in `config.py`, but this one takes `run_dir` instead of `run_id` as an argument.
    """
    if "dir" in key:
        return None
    file_path = run_dir.joinpath(RUN_DIR_STRUCTURE[key])
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
            return json.load(f)
        except json.JSONDecodeError:
            return f.read()


def load_run_request(obj: Dict[str, Any]) -> RunRequestForm:
    wf_attachment = [
        UploadFile(
            file=io.BytesIO(b""),
            filename=f["filename"],
            headers=f["headers"],
            size=f["size"],
        ) for f in obj["workflow_attachment"]
    ]
    obj["workflow_attachment"] = wf_attachment
    return RunRequestForm.model_validate(obj)


def add_crate_metadata(crate: ROCrate) -> None:
    # @id: ro-crate-metadata.json
    profiles = set(_.rstrip("/") for _ in get_norm_value(crate.metadata, "conformsTo"))
    profiles.add(WORKFLOW_PROFILE)
    crate.metadata["conformsTo"] = [{"@id": _} for _ in sorted(profiles)]

    # @id: ./
    crate.root_dataset.append_to("conformsTo", [
        {"@id": "https://w3id.org/ro/wfrun/process/0.1"},
        {"@id": "https://w3id.org/ro/wfrun/workflow/0.1"},
        {"@id": WORKFLOW_PROFILE},
    ])


def add_run_crate_profile(crate: ROCrate) -> None:
    crate.add(CreativeWork(crate, "https://w3id.org/ro/wfrun/process/0.1", properties={
        "name": "Process Run Crate",
        "version": "0.1"
    }))
    crate.add(CreativeWork(crate, "https://w3id.org/ro/wfrun/workflow/0.1", properties={
        "name": "Workflow Run Crate",
        "version": "0.1"
    }))
    crate.add(CreativeWork(crate, "https://w3id.org/workflowhub/workflow-ro-crate/1.0", properties={
        "name": "Workflow RO-Crate",
        "version": "1.0"
    }))


def add_workflow(crate: ROCrate, run_dir: Path, run_request: RunRequestForm) -> None:
    """\
    Modified from crate.add_workflow()

    RunRequest:
      - wf_url: Remote location, or local file path attached as workflow_attachment and downloaded to exe_dir
    """
    wf_url = run_request.workflow_url
    wf_url_parts = urlsplit(wf_url)
    if wf_url_parts.scheme in ["http", "https"]:
        wf_ins = ComputationalWorkflow(crate, wf_url)
    else:
        wf_file_path = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"], wf_url).resolve(strict=True)
        wf_ins = ComputationalWorkflow(crate, wf_file_path, wf_file_path.relative_to(run_dir))
        append_exe_dir_dataset(crate, wf_ins)

    crate.add(wf_ins)
    crate.mainEntity = wf_ins

    wf_ins.lang = generate_wf_lang(crate, run_request)


def update_local_file_stat(file_ins: File, file_path: Path, include_content: bool = True, include_force: bool = False) -> None:
    """\
    Add file stat such as `contentSize` and `sha512` to the file instance given as an argument.
    The instance itself is updated.
    """
    if file_path.is_file() is False:
        return None
    if file_path.exists() is False:
        return None

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
        if include_force or file_ins["contentSize"] < 10 * 1024:
            try:
                file_ins["text"] = file_path.read_text()
            except UnicodeDecodeError:
                pass

    edam = inspect_edam_format(file_path)
    if edam is not None:
        file_ins.append_to("encodingFormat", edam.url, compact=True)
    else:
        # https://pypi.org/project/python-magic/
        file_ins["encodingFormat"] = magic.from_file(str(file_path), mime=True)

    return None


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


def generate_wf_lang(crate: ROCrate, run_request: RunRequestForm) -> ComputerLanguage:
    """\
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


outputs_adapter = TypeAdapter(List[FileObject])


def add_workflow_run(crate: ROCrate, run_dir: Path, run_request: RunRequestForm, run_id: str) -> None:
    # Run metadata
    create_action_ins = ContextEntity(crate, identifier=run_id, properties={
        "@type": "CreateAction",
        "name": "Sapporo workflow run " + run_id
    })
    create_action_ins.append_to("instrument", crate.mainEntity, compact=True)
    crate.root_dataset.append_to("mentions", create_action_ins)

    # Time
    create_action_ins["startTime"] = read_file(run_dir, "start_time", one_line=True)
    create_action_ins["endTime"] = read_file(run_dir, "end_time", one_line=True)

    # Status
    exit_code = read_file(run_dir, "exit_code", one_line=True)
    create_action_ins["exitCode"] = int(exit_code)
    state = read_file(run_dir, "state", one_line=True)
    create_action_ins["wesState"] = state
    if exit_code == "0":
        create_action_ins["actionStatus"] = "CompletedActionStatus"
    else:
        create_action_ins["actionStatus"] = "FailedActionStatus"

    crate.add(create_action_ins)

    # Run inputs
    # All workflow attachments (run_request.workflow_attachment and run_request.workflow_attachment_obj) are treated as workflow inputs.
    # These workflow attachments are placed in exe_dir (downloaded)
    main_wf_id = crate.mainEntity["@id"]
    for attached_file in run_request.workflow_attachment:
        source = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"], str(attached_file.filename))
        dest = source.relative_to(run_dir)
        if str(dest) == str(main_wf_id):
            continue
        file_ins = File(crate, source, dest, properties={
            "@type": "File",
        })
        update_local_file_stat(file_ins, source, include_content=False)
        append_exe_dir_dataset(crate, file_ins)
        crate.add(file_ins)
        create_action_ins.append_to("object", file_ins)
    for attached_item in run_request.workflow_attachment_obj:
        source = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"], attached_item.file_name)
        dest = source.relative_to(run_dir)
        if str(dest) == str(main_wf_id):
            continue
        file_ins = File(crate, source, dest, properties={
            "@type": "File",
            "url": attached_item.file_url,
        })
        update_local_file_stat(file_ins, source, include_content=False)
        append_exe_dir_dataset(crate, file_ins)
        crate.add(file_ins)
        create_action_ins.append_to("object", file_ins)

    # Run outputs
    outputs = outputs_adapter.validate_python(read_file(run_dir, "outputs") or [])
    for source in run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"]).glob("**/*"):
        if source.is_dir():
            continue

        file_apath = source.resolve(strict=True)
        file_rpath = file_apath.relative_to(run_dir)

        actual_file = File(crate, file_apath, file_rpath, properties={
            "@type": "File",
        })
        update_local_file_stat(actual_file, file_apath)

        if outputs is not None:
            # Include the URL of Sapporo's download feature
            output_dir_dest = file_apath.relative_to(run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"]))
            for output in outputs:
                if str(output.file_name) == str(output_dir_dest):
                    actual_file["url"] = output.file_url

        add_file_stats(crate, actual_file)
        append_outputs_dir_dataset(crate, actual_file)

        create_action_ins.append_to("result", actual_file)
        crate.add(actual_file)

    # Log files
    # Add log files
    log_files: List[Tuple[RunDirStructureKeys, str]] = [
        ("stdout", "Sapporo stdout"),
        ("stderr", "Sapporo stderr"),
    ]
    for key, name in log_files:
        source = run_dir.joinpath(RUN_DIR_STRUCTURE[key])
        if source.exists() is False:
            continue
        dest = source.relative_to(run_dir)
        file_ins = File(crate, source, dest, properties={
            "name": name,
        })
        update_local_file_stat(file_ins, source)
        create_action_ins.append_to("subjectOf", file_ins)
        crate.add(file_ins)

    # MultiQC stats
    add_multiqc_stats(crate, run_dir, create_action_ins)


def add_multiqc_stats(crate: ROCrate, run_dir: Path, create_action_ins: ContextEntity) -> None:
    """\
    Run multiqc and add multiqc stats to crate
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            multiqc.run(str(run_dir), outdir=str(run_dir), data_format="json", no_report=True, quiet=True)
    except Exception:  # pylint: disable=broad-except
        print(stderr.getvalue(), file=sys.stderr)
        return

    multiqc_data_dir = run_dir.joinpath("multiqc_data")
    multiqc_stats = run_dir.joinpath(RUN_DIR_STRUCTURE["multiqc_stats"])
    if multiqc_data_dir.exists() and multiqc_data_dir.joinpath("multiqc_general_stats.json").exists():
        shutil.move(str(multiqc_data_dir.joinpath("multiqc_general_stats.json")), str(multiqc_stats))
        shutil.rmtree(str(multiqc_data_dir))

    if multiqc_stats.exists() is False:
        # Do nothing, TODO: logging or not?
        return

    file_ins = File(crate, multiqc_stats, multiqc_stats.relative_to(run_dir), properties={
        "name": "MultiQC stats",
    })
    update_local_file_stat(file_ins, multiqc_stats, include_content=True, include_force=True)
    create_action_ins.append_to("multiqcStats", file_ins)
    crate.add(file_ins)


def add_file_stats(crate: ROCrate, file_ins: File) -> None:
    """\
    see "format" field of file_ins

    ".bam": "http://edamontology.org/format_2572"
    ".sam": "http://edamontology.org/format_2573",
      -> quay.io/biocontainers/samtools:1.15.1--h1170115_0
    ".vcf": "http://edamontology.org/format_3016",
      -> quay.io/biocontainers/vcftools:0.1.16--pl5321h9a82719_6
    """
    if shutil.which("docker") is None:
        return

    formats = get_norm_value(file_ins, "encodingFormat")
    for format_ in formats:
        if format_ in ("http://edamontology.org/format_2572", "http://edamontology.org/format_2573"):
            # bam or sam
            add_samtools_stats(crate, file_ins)
        elif format_ == "http://edamontology.org/format_3016":
            # vcf
            add_vcftools_stats(crate, file_ins)


def add_samtools_stats(crate: ROCrate, file_ins: File) -> None:
    """\
    $ samtools flagstats --output-fmt json <file_path>

    Using: quay.io/biocontainers/samtools:1.15.1--h1170115_0
    """
    source = file_ins.source
    cmd = shlex.split(" ".join([
        "docker",
        "run",
        "--rm",
        "-v",
        f"{source}:/work/{source.name}",
        "-w",
        "/work",
        "quay.io/biocontainers/samtools:1.15.1--h1170115_0",
        "samtools",
        "flagstats",
        "--output-fmt",
        "json",
        source.name,
    ]))
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        return
    try:
        stats = json.loads(proc.stdout)
        total = stats["QC-passed reads"]["total"]
        mapped = stats["QC-passed reads"]["mapped"]
        unmapped = total - mapped
        duplicate = stats["QC-passed reads"]["duplicates"]
        stats_ins = ContextEntity(crate, properties={
            "@type": ["FileStats"],
            "totalReads": total,
            "mappedReads": mapped,
            "unmappedReads": unmapped,
            "duplicateReads": duplicate,
            "mappedRate": mapped / total,
            "unmappedRate": unmapped / total,
            "duplicateRate": duplicate / total,
        })
        stats_ins.append_to("generatedBy", find_or_generate_software_ins(crate, "samtools", "1.15.1--h1170115_0"), compact=True)
        file_ins.append_to("stats", stats_ins, compact=True)
        crate.add(stats_ins)
    except json.JSONDecodeError:
        return


def add_vcftools_stats(crate: ROCrate, file_ins: File) -> None:
    """\
    $ vcf-stats <file_path>

    Using: quay.io/biocontainers/vcftools:0.1.16--pl5321h9a82719_6
    """
    source = file_ins.source
    cmd = shlex.split(" ".join([
        "docker",
        "run",
        "--rm",
        "-v",
        f"{source}:/work/{source.name}",
        "-w",
        "/work",
        "quay.io/biocontainers/vcftools:0.1.16--pl5321h9a82719_6",
        "vcf-stats",
        source.name,
    ]))
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        return
    try:
        stdout = proc.stdout.decode()
        stdout = stdout.strip()
        stdout = stdout.lstrip("$VAR1 = ")
        stdout = stdout.rstrip(";")
        stdout = stdout.replace("=>", ":")
        stdout = stdout.replace("\'", "\"")
        stats = json.loads(stdout)
        stats_ins = ContextEntity(crate, properties={
            "@type": ["FileStats"],
            "variantCount": stats["all"].get("count", 0),
            "snpsCount": stats["all"].get("snp_count", 0),
            "indelsCount": stats["all"].get("indel_count", 0),
        })
        stats_ins.append_to("generatedBy", find_or_generate_software_ins(crate, "vcftools", "0.1.16--pl5321h9a82719_6"), compact=True)
        file_ins.append_to("stats", stats_ins, compact=True)
        crate.add(stats_ins)
    except json.JSONDecodeError:
        return


def find_or_generate_software_ins(crate: ROCrate, name: str, version: str) -> SoftwareApplication:
    for entity in crate.get_entities():
        if isinstance(entity, SoftwareApplication):
            if entity["name"] == name:
                return entity
    software_ins = SoftwareApplication(crate, identifier=name, properties={
        "name": name,
        "version": version
    })
    crate.add(software_ins)

    return software_ins


def append_outputs_dir_dataset(crate: ROCrate, ins: DataEntity) -> None:
    for entity in crate.get_entities():
        if isinstance(entity, Dataset):
            if str(entity["@id"]) == f"{RUN_DIR_STRUCTURE['outputs_dir']}/":
                entity.append_to("hasPart", ins, compact=True)


def extract_exe_dir_file_ids(crate: ROCrate) -> List[str]:
    for entity in crate.get_entities():
        if isinstance(entity, Dataset):
            if str(entity["@id"]) == f"{RUN_DIR_STRUCTURE['exe_dir']}/":
                return get_norm_value(entity, "hasPart")
    return []


# === main ===


if __name__ == "__main__":
    inputted_dir = Path(sys.argv[1]).resolve(strict=True)
    generate_ro_crate(str(inputted_dir))
