#!/usr/bin/env python3
# coding: utf-8
import json
from pathlib import Path
from typing import BinaryIO, Dict, Tuple

import requests
from requests import Response

from sapporo.type import RunRequest

URL: str = "localhost:8080"
SCRIPT_DIR: Path = \
    Path(__file__).parent.resolve()
RES_D: Path = \
    SCRIPT_DIR.parent.joinpath("resources").resolve()


def main() -> None:
    data: RunRequest = {
        "workflow_params": json.dumps({
            "fastq_1": {
                "class": "File",
                "location": "https://raw.githubusercontent.com/ddbj/" +
                            "SAPPORO-service/blob/feature/" +
                            "follow-original-wes/tests/resources/" +
                            "ERR034597_1.small.fq.gz"
            },
            "fastq_2": {
                "class": "File",
                "location": "https://raw.githubusercontent.com/ddbj/" +
                            "SAPPORO-service/blob/feature/" +
                            "follow-original-wes/tests/resources/" +
                            "ERR034597_2.small.fq.gz"
            }
        }),
        "workflow_type": "CWL",
        "workflow_type_version": "v1.0",
        "tags": json.dumps({
            "workflow_name": "trimming_and_qc_remote"
        }),
        "workflow_engine_name": "cwltool",
        "workflow_engine_parameters": json.dumps({}),
        "workflow_url": "https://raw.githubusercontent.com/ddbj/" +
                        "SAPPORO-service/blob/feature/follow-original-wes" +
                        "/tests/resources/trimming_and_qc_remote.cwl"
    }
    files: Dict[str, Tuple[str, BinaryIO]] = {}
    response: Response = \
        requests.post(f"http://{URL}/runs", data=data, files=files)

    print(response.status_code)
    print(json.dumps(json.loads(response.text), indent=2))


if __name__ == "__main__":
    main()
