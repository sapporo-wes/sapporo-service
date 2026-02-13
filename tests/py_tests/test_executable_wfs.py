import json
import logging

import pytest

from .conftest import anyhow_get_test_client, post_run
from .test_run_cwltool import attach_all_run_request


def test_post_invalid_wf(mocker, tmpdir):  # type: ignore[no-untyped-def]
    from sapporo.config import AppConfig

    executable_wfs = tmpdir.joinpath("executable_workflows.json")
    with executable_wfs.open("w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "workflows": [
                        "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimming_and_qc.cwl"
                    ]
                }
            )
        )
    app_config = AppConfig(executable_workflows=executable_wfs)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    response = post_run(client, **attach_all_run_request)  # type: ignore[arg-type]
    assert response.status_code == 400


def test_get_executable_wfs(mocker, tmpdir):  # type: ignore[no-untyped-def]
    from sapporo.config import AppConfig

    executable_wfs = tmpdir.joinpath("executable_workflows.json")
    with executable_wfs.open("w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "workflows": [
                        "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimming_and_qc.cwl"
                    ]
                }
            )
        )
    app_config = AppConfig(executable_workflows=executable_wfs)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    response = client.get("/executable-workflows")
    assert response.status_code == 200
    data = response.json()

    assert data["workflows"] == [
        "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimming_and_qc.cwl"
    ]


def test_not_remote_wfs(mocker, tmpdir):  # type: ignore[no-untyped-def]
    from sapporo.app import init_app_state
    from sapporo.config import AppConfig

    executable_wfs = tmpdir.joinpath("executable_workflows.json")
    with executable_wfs.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"workflows": ["trimming_and_qc.cwl"]}))
    app_config = AppConfig(executable_workflows=executable_wfs)
    anyhow_get_test_client(app_config, mocker, tmpdir)

    logging.getLogger("sapporo").setLevel(logging.WARNING)
    with pytest.raises(ValueError):
        init_app_state()
