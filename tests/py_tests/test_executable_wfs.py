# pylint: disable=C0415, W0613, W0621
import json

from .conftest import anyhow_get_test_client, post_run
from .test_post_cwltool import attach_all_run_request


def test_executable_wfs(mocker, tmpdir):  # type: ignore
    from sapporo.config import AppConfig

    executable_wfs = tmpdir.joinpath("executable_workflows.json")
    with executable_wfs.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"workflows": ["https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimming_and_qc.cwl"]}))
    app_config = AppConfig(executable_workflows=executable_wfs)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    response = post_run(client, **attach_all_run_request)  # type: ignore
    assert response.status_code == 400
