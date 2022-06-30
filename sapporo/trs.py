#!/usr/bin/env python3
# coding: utf-8
from typing import Any, List

import requests

from sapporo.model import Workflow


def get_wfs(trs_endpoint: str) -> List[Workflow]:
    try:
        if not is_trs_endpoint(trs_endpoint):
            raise ValueError(f"Invalid TRS endpoint: {trs_endpoint}")
    except Exception as e:
        raise ValueError(f"Invalid TRS endpoint: {trs_endpoint} ({e})")
    try:
        return get_wfs_via_api(trs_endpoint)
    except Exception as e:
        raise ValueError(f"Failed to get TRS workflow list ({e})")


def get_service_info(trs_endpoint: str) -> Any:
    url = trs_endpoint.rstrip("/") + "/service-info"
    res = requests.get(url, allow_redirects=True)
    if res.status_code != 200:
        raise Exception("Failed to get service info")
    return res.json()


def is_trs_endpoint(trs_endpoint: str) -> bool:
    service_info = get_service_info(trs_endpoint)
    try:
        _type = service_info["type"]
        artifact = _type["artifact"]
        version = _type["version"]
    except Exception:
        raise ValueError(f"Invalid TRS endpoint: {trs_endpoint}")
    if artifact.lower() in ["trs", "gh-trs", "yevis"] and version.startswith("2."):
        return True
    return False


def get_tools(trs_endpoint: str) -> Any:
    url = trs_endpoint.rstrip("/") + "/tools"
    res = requests.get(url, allow_redirects=True)
    if res.status_code != 200:
        raise Exception("Failed to get tools")
    return res.json()


def get_wfs_via_api(trs_endpoint: str) -> List[Workflow]:
    tools = get_tools(trs_endpoint)
    wfs = []
    for tool in tools:
        try:
            _id = tool["id"]
            for ver in tool["versions"]:
                name = ver["name"]
                version = ver["id"]
                for _type in ver["descriptor_type"]:
                    wf: Workflow = {
                        "workflow_name": name + f": {version}",
                        "workflow_url": "",
                        "workflow_type": fix_wf_type(_type),
                        "workflow_type_version": ret_wf_type_version(_type),
                        "workflow_attachment": []
                    }
                    files = get_files_via_api(trs_endpoint, _id, version, _type)
                    for file in files:
                        url = file["path"]
                        if file["file_type"] == "PRIMARY_DESCRIPTOR":
                            wf["workflow_url"] = url
                        elif file["file_type"] == "SECONDARY_DESCRIPTOR":
                            wf["workflow_attachment"].append({
                                "file_name": url.split("/")[-1],
                                "file_url": url
                            })
                    if wf["workflow_url"] != "":
                        wfs.append(wf)
        except Exception:
            pass
    return wfs


def get_files_via_api(trs_endpoint: str, id: str, ver: str, _type: str) -> Any:
    url = trs_endpoint.rstrip("/") + f"/tools/{id}/versions/{ver}/{_type}/files"
    res = requests.get(url, allow_redirects=True)
    if res.status_code != 200:
        raise Exception("Failed to get files")
    return res.json()


def fix_wf_type(_type: str) -> str:
    _type = _type.lower()
    if _type == "cwl":
        return "CWL"
    elif _type == "wdl":
        return "WDL"
    elif _type == "nfl" or _type == "nextflow":
        return "NFL"
    elif _type == "smk" or _type == "snakemake":
        return "SMK"
    else:
        return _type


def ret_wf_type_version(_type: str) -> str:
    _type = _type.lower()
    if _type == "cwl":
        return "v1.0"
    elif _type == "wdl":
        return "1.0"
    elif _type == "nfl" or _type == "nextflow":
        return "1.0"
    elif _type == "smk" or _type == "snakemake":
        return "1.0"
    else:
        return "1.0"
