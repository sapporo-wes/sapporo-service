#!/usr/local/bin/python3
# coding: utf-8
from typing import Dict, List

import requests
from requests.exceptions import RequestException

from flask import abort

from .util import read_workflow_info


def generate_workflow_list() -> Dict[str, List[Dict[str, str]]]:
    workflow_info = read_workflow_info()
    data: Dict[str, List[Dict[str, str]]] = dict()
    data["workflows"] = []
    for workflow in workflow_info["workflows"]:
        workflow["workflow_content"] = \
            fetch_file(workflow["workflow_location"])
        workflow["workflow_parameters_template"] = \
            fetch_file(workflow["workflow_parameters_template_location"])
        data["workflows"].append(workflow)

    return data


def fetch_file(url: str) -> str:
    try:
        response = requests.get(url)
        response.raise_for_status()
    except RequestException:
        abort(500, "Can not get file: {}".format(url))

    return response.content.decode()
