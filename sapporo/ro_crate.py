#!/usr/bin/env python3
# coding: utf-8
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

TERM_PATH = Path(__file__).parent.joinpath("ro-terms.csv")
TERM_URL_BASE = "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/ro-terms.csv"
SAPPORO_EXTRA_TERMS: Dict[str, str] = {}
with TERM_PATH.open(mode="r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("term"):
            continue
        term = line.strip().split(",")[0]
        SAPPORO_EXTRA_TERMS[term] = f"{TERM_URL_BASE}#{term}"

# https://www.researchobject.org/ro-terms/
# https://www.researchobject.org/ro-terms/#why-are-terms-collected-in-a-csv
TESTING_EXTRA_TERMS: Dict[str, str] = {
    "TestSuite": "https://w3id.org/ro/terms/test#TestSuite",
    "TestInstance": "https://w3id.org/ro/terms/test#TestInstance",
    "TestService": "https://w3id.org/ro/terms/test#TestService",
    "TestDefinition": "https://w3id.org/ro/terms/test#TestDefinition",
    "instance": "https://w3id.org/ro/terms/test#instance",
    "runsOn": "https://w3id.org/ro/terms/test#runsOn",
    "resource": "https://w3id.org/ro/terms/test#resource",
    "definition": "https://w3id.org/ro/terms/test#definition",
    "engineVersion": "https://w3id.org/ro/terms/test#engineVersion",
}

# https://www.researchobject.org/ro-crate/1.1/metadata.html#additional-metadata-standards
# - https://bioschemas.org/ComputationalWorkflow
# - https://bioschemas.org/FormalParameter
# - https://bioschemas.org/ComputationalWorkflow#input
# - https://bioschemas.org/ComputationalWorkflow#output

# === type definitions ===


class SapporoConfig(TypedDict):
    sapporo_version: str
    get_runs: bool
    workflow_attachment: bool
    registered_only_mode: bool
    service_info: str
    executable_workflows: str
    run_sh: str
    url_prefix: str
    sapporo_endpoint: str


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


# === functions ===


def generate_ro_crate(inputted_run_dir: str) -> None:
    """\
    Called in run.sh
    """
    run_dir: Path = Path(inputted_run_dir).resolve(strict=True)
    if not run_dir.is_dir():
        raise NotADirectoryError(f"{run_dir} is not a directory.")
    run_request: RunRequest = read_file(run_dir, "run_request")
    sapporo_config: SapporoConfig = read_file(run_dir, "sapporo_config")
    service_info: ServiceInfo = read_file(run_dir, "service_info")
    yevis_metadata: Optional[YevisMetadata] = read_file(run_dir, "yevis_metadata")
    run_id = run_dir.name

    crate = ROCrate(init=False, gen_preview=False)
    add_root_data_entity(crate, yevis_metadata)
    add_dataset_dir(crate, run_dir)
    add_workflow(crate, run_dir, run_request, yevis_metadata)
    add_workflow_attachment(crate, run_dir, run_request, yevis_metadata)
    add_test(crate, run_dir, run_request, sapporo_config, service_info, yevis_metadata, run_id)

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


def add_root_data_entity(crate: ROCrate, yevis_meta: Optional[YevisMetadata]) -> None:
    """\
    Modified from crate.__init__from_tree()

    https://www.researchobject.org/ro-crate/1.1/root-data-entity.html#direct-properties-of-the-root-data-entity
    """
    root_dataset_ins = RootDataset(crate, properties={
        "name": "Sapporo RO-Crate",
        "description": "RO-Crate of Sapporo's run execution results.",
    })
    metadata_ins = Metadata(crate)
    metadata_ins.extra_terms.update(SAPPORO_EXTRA_TERMS)

    if yevis_meta is not None:
        root_dataset_ins.append_to("license", generate_license(crate, yevis_meta), compact=True)
        authors = yevis_meta["authors"]
        for author in authors:
            root_dataset_ins.append_to("author", generate_person(crate, author), compact=True)

    crate.add(
        root_dataset_ins,
        metadata_ins,
    )


def generate_license(crate: ROCrate, yevis_meta: YevisMetadata) -> ContextEntity:
    """\
    Call GitHub REST API to get license information.
    """
    license = yevis_meta["license"]
    with urllib.request.urlopen(f"https://api.github.com/licenses/{license}") as f:
        if f.status == 200:
            license_info = json.load(f)
            name = license_info["name"]
            id_ = license_info["html_url"]
        else:
            name = license
            id_ = license
    license_ins = ContextEntity(crate, id_, properties={
        "@type": ["CreativeWork"],
        "name": name,
    })

    crate.add(license_ins)

    return license_ins


def generate_person(crate: ROCrate, author: YevisAuthor) -> ContextEntity:
    if "orcid" in author:
        id_ = f"https://orcid.org/{author['orcid']}"
    else:
        id_ = f"https://github.com/{author['github_account']}"
    person_ins = ContextEntity(crate, id_, properties={
        "@type": ["Person"],
        "name": author["name"],
        "affiliation": author["affiliation"],
    })

    crate.add(person_ins)

    return person_ins


def add_dataset_dir(crate: ROCrate, run_dir: Path) -> None:
    exe_dir = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"])
    crate.add_dataset(
        exe_dir, exe_dir.relative_to(run_dir), {
            "name": "Sapporo execution directory",
        }
    )
    outputs_dir = run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"])
    crate.add_dataset(
        outputs_dir, outputs_dir.relative_to(run_dir), {
            "name": "Sapporo outputs directory",
        }
    )


def append_exe_dir_dataset(crate: ROCrate, ins: DataEntity) -> None:
    for entity in crate.get_entities():
        if isinstance(entity, Dataset):
            if str(entity["@id"]) == f"{RUN_DIR_STRUCTURE['exe_dir']}/":
                entity.append_to("hasPart", ins, compact=True)


def append_outputs_dir_dataset(crate: ROCrate, ins: DataEntity) -> None:
    for entity in crate.get_entities():
        if isinstance(entity, Dataset):
            if str(entity["@id"]) == f"{RUN_DIR_STRUCTURE['outputs_dir']}/":
                entity.append_to("hasPart", ins, compact=True)


def add_workflow(crate: ROCrate, run_dir: Path, run_request: RunRequest, yevis_meta: Optional[YevisMetadata]) -> None:
    """\
    Modified from crate.add_workflow()

    RunRequest:
      - wf_url: Remote location, or local file path attached as workflow_attachment and downloaded to exe_dir
    """
    wf_url = cast(str, run_request["workflow_url"])
    wf_url_parts = urlsplit(wf_url)
    if wf_url_parts.scheme == "http" or wf_url_parts.scheme == "https":
        tmp_file_path, _ = urllib.request.urlretrieve(wf_url)
        wf_file_path = Path(tmp_file_path)
        wf_ins = ComputationalWorkflow(crate, wf_url)
        update_local_file_stat(crate, wf_ins, wf_file_path)
        del wf_ins["dateModified"]
        del wf_ins["uid"]
        del wf_ins["gid"]
        del wf_ins["mode"]
    else:
        wf_file_path = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"], wf_url).resolve(strict=True)
        wf_ins = ComputationalWorkflow(crate, wf_file_path, wf_file_path.relative_to(run_dir))
        update_local_file_stat(crate, wf_ins, wf_file_path)
        append_exe_dir_dataset(crate, wf_ins)

    crate.add(wf_ins)

    if run_request["workflow_name"] is not None:
        wf_ins["name"] = run_request["workflow_name"]

    wf_ins.lang = generate_wf_lang(crate, run_request)

    crate.mainEntity = wf_ins
    profiles = set(_.rstrip("/") for _ in get_norm_value(crate.metadata, "conformsTo"))
    profiles.add(WORKFLOW_PROFILE)
    crate.metadata["conformsTo"] = [{"@id": _} for _ in sorted(profiles)]

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

    # additional properties (not defined)
    file_ins["uid"] = stat_result.st_uid
    file_ins["gid"] = stat_result.st_gid
    file_ins["mode"] = stat.filemode(stat_result.st_mode)

    # add file line count
    try:
        file_ins["lineCount"] = count_lines(file_path)
    except UnicodeDecodeError:
        pass

    # checksum using sha512 (https://www.researchobject.org/ro-crate/1.1/appendix/implementation-notes.html#combining-with-other-packaging-schemes)
    file_ins["sha512"] = generate_sha512(file_path)

    # https://pypi.org/project/python-magic/
    file_ins["encodingFormat"] = magic.from_file(file_path, mime=True)

    if include_content:
        # under 10kb, attach as text
        if file_ins["contentSize"] < 10 * 1024:
            try:
                file_ins["text"] = file_path.read_text()
            except UnicodeDecodeError:
                pass

    edam = inspect_edam_format(file_path)
    if edam is not None:
        edam_ins = ContextEntity(crate, edam["url"], properties={
            "@type": ["Format"],
            "name": edam["name"],
        })
        crate.add(edam_ins)
        file_ins.append_to("format", edam_ins, compact=True)


def count_lines(file_path: Path) -> int:
    block_size = 65536
    count = 0
    with file_path.open("r") as f:
        while True:
            buffer = f.read(block_size)
            if not buffer:
                break
            count += buffer.count("\n")

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

    return sha512.hexdigest()


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


def add_test(crate: ROCrate, run_dir: Path, run_request: RunRequest,
             sapporo_config: SapporoConfig, service_info: ServiceInfo, yevis_meta: Optional[YevisMetadata], run_id: str) -> None:
    suite_ins = generate_test_suite(crate)
    crate.root_dataset.append_to("about", suite_ins, compact=True)

    test_ins = generate_test_instance(crate, sapporo_config)
    suite_ins.append_to("instance", test_ins, compact=True)

    test_service_ins = generate_sapporo_service(crate, run_dir, sapporo_config)
    test_ins.service = test_service_ins  # runsOn

    test_env_ins = generate_test_env(crate)
    test_ins.append_to("environment", test_env_ins, compact=True)

    test_definition_ins = generate_test_definition(crate, run_dir, run_request, service_info, yevis_meta)
    suite_ins.definition = test_definition_ins

    test_result_ins = generate_test_result(crate, run_dir, run_id)
    suite_ins.append_to("result", test_result_ins, compact=True)

    crate.metadata.extra_terms.update(TESTING_EXTRA_TERMS)


def generate_test_suite(crate: ROCrate) -> TestInstance:
    """\
    Modified from crate.add_test_suite()

    TestSuite: A set of tests for a computational workflow
      - instance: Instances of a test suite
      - definition: Metadata describing how to run the test
    """
    suite_ins = TestSuite(crate, identifier="sapporo-test-suite")
    suite_ins.name = "Sapporo test suite"
    suite_ins["mainEntity"] = crate.mainEntity

    crate.add(suite_ins)

    return suite_ins


def generate_test_instance(crate: ROCrate, sapporo_config: SapporoConfig) -> TestInstance:
    """\
    Modified from crate.add_test_instance()

    TestInstance: A specific project to execute a test suite on a test service
      - runsOn: Service where the test instance is executed
    """
    test_ins = TestInstance(crate, identifier="sapporo-test-instance")
    test_ins.url = sapporo_config["sapporo_endpoint"]
    test_ins.name = "Sapporo test instance"

    crate.add(test_ins)

    return test_ins


def generate_sapporo_service(crate: ROCrate, run_dir: Path, sapporo_config: SapporoConfig) -> TestService:
    """\
    TestService: A software service where tests can be run
      - resource: Relative URL of the test project on the service
    """
    test_service_ins = TestService(crate, identifier="sapporo-service", properties={
        "@type": ["TestService", "SapporoService", "SoftwareApplication"],
        "name": "Sapporo-service",
        "version": sapporo_config["sapporo_version"],
        "resource": sapporo_config["url_prefix"]  # relative URL
    })
    crate.add(test_service_ins)
    sapporo_url_ins = ContextEntity(
        crate,
        "https://github.com/sapporo-wes/sapporo-service",
        properties={
            "@type": ["WebPage"],
        })
    test_service_ins.append_to("url", sapporo_url_ins, compact=True)
    crate.add(sapporo_url_ins)

    # Generate runtime parameters for Sapporo-service
    sapporo_conf_ins = ContextEntity(crate, identifier="sapporo-config", properties={
        "@type": ["SapporoConfiguration"],
        "getRuns": sapporo_config["get_runs"],
        "workflowAttachment": sapporo_config["workflow_attachment"],
        "registeredOnlyMode": sapporo_config["registered_only_mode"],
        "urlPrefix": sapporo_config["url_prefix"],
        "sapporoEndpoint": sapporo_config["sapporo_endpoint"],
    })
    test_service_ins.append_to("configuration", sapporo_conf_ins, compact=True)
    crate.add(sapporo_conf_ins)

    # Add local files about service-info, executable-workflows, run.sh, sapporo_config.json
    files: List[Tuple[RUN_DIR_STRUCTURE_KEYS, str, str]] = [
        ("service_info", "serviceInfo", "Sapporo service info"),
        ("executable_workflows", "executableWorkflows", "Sapporo executable workflows"),
        ("run_sh", "runSh", "Sapporo run.sh"),
        ("sapporo_config", "sapporoConfig", "Sapporo runtime configuration"),
    ]
    for key, field_key, name in files:
        source = run_dir.joinpath(RUN_DIR_STRUCTURE[key])
        if source.exists() is False:
            continue
        dest = source.relative_to(run_dir)
        file_ins = File(crate, source, dest, properties={
            "name": name,
        })
        update_local_file_stat(crate, file_ins, source)
        sapporo_conf_ins.append_to(field_key, file_ins, compact=True)
        crate.add(file_ins)

    return test_service_ins


def generate_test_env(crate: ROCrate) -> ContextEntity:
    """\
    Generate computational environment of the test instance
    """
    uname = platform.uname()
    in_docker = os.path.exists("/.dockerenv")
    test_env_ins = ContextEntity(crate, identifier="sapporo-test-environment", properties={
        "@type": ["TestEnvironment"],
        "os": uname.system,
        "osVersion": uname.release,
        "cpuArchitecture": uname.machine,
        "cpuCount": psutil.cpu_count(),
        "totalMemory": psutil.virtual_memory().total,
        "freeDiskSpace": psutil.disk_usage("/").free,
        "uid": os.getuid(),
        "gid": os.getgid(),
        "inDocker": in_docker,
    })

    crate.add(test_env_ins)

    return test_env_ins


def generate_test_definition(crate: ROCrate, run_dir: Path, run_request: RunRequest,
                             service_info: ServiceInfo, yevis_meta: Optional[YevisMetadata]) -> TestDefinition:
    """\
    Modified from crate.add_test_definition()
    """
    source = run_dir.joinpath(RUN_DIR_STRUCTURE["run_request"])
    dest = source.relative_to(run_dir)
    test_def_ins = TestDefinition(crate, source, dest, properties={
        "@type": ["TestDefinition", "File"],
        "name": "Sapporo run request",
    })
    update_local_file_stat(crate, test_def_ins, source)
    crate.add(test_def_ins)

    # workflow parameter files
    files: List[Tuple[RUN_DIR_STRUCTURE_KEYS, str, str]] = [
        ("wf_params", "workflowParameters", "Sapporo workflow parameters"),
        ("wf_engine_params", "workflowEngineParameters", "Sapporo workflow engine parameters"),
        ("yevis_metadata", "yevisMetadata", "Yevis metadata"),
    ]
    for key, field_key, name in files:
        source = run_dir.joinpath(RUN_DIR_STRUCTURE[key])
        if not source.exists():
            continue
        dest = source.relative_to(run_dir)
        file_ins = File(crate, source, dest, properties={
            "@type": ["File"],
            "name": name,
        })
        if yevis_meta is not None:
            file_obj = [f for f in yevis_meta["workflow"]["testing"][0]["files"] if f["type"] == key]
            if len(file_obj) > 0:
                file_ins["url"] = file_obj[0]["url"]
        update_local_file_stat(crate, file_ins, source)
        if key == "wf_params":
            append_exe_dir_dataset(crate, file_ins)
        test_def_ins.append_to(field_key, file_ins, compact=True)
        crate.add(file_ins)

    # cmd
    cmd_str = read_file(run_dir, "cmd", one_line=True)
    test_def_ins["cmd"] = cmd_str

    # workflow engine
    wf_engine_name = run_request["workflow_engine_name"]
    wf_engine_version = service_info["workflow_engine_versions"][wf_engine_name]  # validated at run acceptance
    wf_engine_ins = generate_wf_engine(crate, wf_engine_name, wf_engine_version)
    test_def_ins.engine = wf_engine_ins
    test_def_ins.engineVersion = wf_engine_version

    if yevis_meta is not None:
        test_def_ins["yevisTestId"] = yevis_meta["workflow"]["testing"][0]["id"]

        # add test data
        test_files = [f for f in yevis_meta["workflow"]["testing"][0]["files"] if f["type"] == "other"]
        for test_file in test_files:
            source = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"], test_file["target"])
            if source.exists() is False:
                continue
            dest = source.relative_to(run_dir)
            file_ins = File(crate, source, dest, properties={
                "@type": ["File", "FormalParameter"],
                "url": test_file["url"],
            })
            update_local_file_stat(crate, file_ins, source)
            append_exe_dir_dataset(crate, file_ins)
            test_def_ins.append_to("input", file_ins, compact=True)
            crate.add(file_ins)

    return test_def_ins


def generate_wf_engine(crate: ROCrate, wf_engine_name: str, wf_engine_version: str) -> SoftwareApplication:
    urls = {
        "cwltool": "https://github.com/common-workflow-language/cwltool",
        "cromwell": "https://cromwell.readthedocs.io/en/stable/",
        "nextflow": "https://www.nextflow.io",
        "snakemake": "https://snakemake.readthedocs.io/en/stable/",
    }
    engine = SoftwareApplication(
        crate,
        identifier=wf_engine_name,
        properties={
            "name": wf_engine_name,
            "version": wf_engine_version,
        })
    if urls.get(wf_engine_name) is not None:
        ctx = ContextEntity(crate, urls[wf_engine_name], properties={
            "@type": ["WebPage"],
        })
        engine.append_to("url", ctx, compact=True)
        crate.add(ctx)

    crate.add(engine)

    return engine


def generate_test_result(crate: ROCrate, run_dir: Path, run_id: str) -> ContextEntity:
    test_result_ins = ContextEntity(crate, identifier="sapporo-test-result", properties={
        "@type": ["TestResult"],
        "name": "Sapporo test result",
    })
    crate.add(test_result_ins)

    test_result_ins["runId"] = run_id

    # Add one-line text files
    one_line_files: List[Tuple[RUN_DIR_STRUCTURE_KEYS, str]] = [
        ("start_time", "startTime"),
        ("end_time", "endTime"),
        ("exit_code", "exitCode"),
        ("pid", "pid"),
        ("state", "state"),
    ]
    for key, field_key in one_line_files:
        content = read_file(run_dir, key, one_line=True)
        if content is None:
            continue
        if key == "pid" or key == "exit_code":
            test_result_ins[field_key] = int(content)
        else:
            test_result_ins[field_key] = content

    # Add log files
    log_files: List[Tuple[RUN_DIR_STRUCTURE_KEYS, str, str]] = [
        ("stdout", "stdout", "Sapporo stdout"),
        ("stderr", "stderr", "Sapporo stderr"),
        ("task_logs", "taskLogs", "Sapporo task logs"),
    ]
    for key, field_key, name in log_files:
        source = run_dir.joinpath(RUN_DIR_STRUCTURE[key])
        if source.exists() is False:
            continue
        dest = source.relative_to(run_dir)
        file_ins = File(crate, source, dest, properties={
            "name": name,
        })
        update_local_file_stat(crate, file_ins, source)
        test_result_ins.append_to(field_key, file_ins, compact=True)
        crate.add(file_ins)

    # Add output files
    outputs: Optional[List[AttachedFile]] = read_file(run_dir, "outputs")
    for source in run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"]).glob("**/*"):
        if source.is_dir():
            continue
        source = source.resolve(strict=True)
        dest = source.relative_to(run_dir)
        file_ins = File(crate, source, dest, properties={
            "@type": ["File", "FormalParameter", "OutputFile"],
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
        test_result_ins.append_to("outputs", file_ins, compact=True)
        crate.add(file_ins)

    # Add intermediate files
    test_result_ins["intermediateFiles"] = []
    already_added_ids = extract_exe_dir_file_ids(crate)
    for source in run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"]).glob("**/*"):
        if source.is_dir():
            continue
        source = source.resolve(strict=True)
        dest = source.relative_to(run_dir)
        if str(dest) in already_added_ids:
            continue
        file_ins = File(crate, source, dest, properties={
            "@type": ["File", "FormalParameter", "IntermediateFile"],
        })
        update_local_file_stat(crate, file_ins, source, include_content=False)
        append_exe_dir_dataset(crate, file_ins)
        test_result_ins.append_to("intermediateFiles", file_ins, compact=True)
        crate.add(file_ins)

    return test_result_ins


def extract_exe_dir_file_ids(crate: ROCrate) -> List[str]:
    for entity in crate.get_entities():
        if isinstance(entity, Dataset):
            if str(entity["@id"]) == f"{RUN_DIR_STRUCTURE['exe_dir']}/":
                return cast(List[str], get_norm_value(entity, "hasPart"))
    return []


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
    proc = subprocess.run(cmd, capture_output=True)
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
    proc = subprocess.run(cmd, capture_output=True)
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


if __name__ == "__main__":
    import sys
    inputted_dir = Path(sys.argv[1]).resolve(strict=True)
    generate_ro_crate(str(inputted_dir))
