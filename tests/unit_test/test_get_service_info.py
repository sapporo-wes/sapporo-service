# coding: utf-8
# pylint: disable=unused-argument
from pathlib import Path

from flask.testing import FlaskClient

from .conftest import get_default_config, setup_test_client


def test_get_service_info(delete_env_vars: None, test_client: FlaskClient) -> None:  # type: ignore
    res = test_client.get("/service-info")
    res_data = res.get_json()

    expected = {
        "auth_instructions_url": "https://github.com/sapporo-wes/sapporo-service",
        "contact_info_url": "https://github.com/sapporo-wes/sapporo-service",
        "default_workflow_engine_parameters": {
            "nextflow": [
                {"default_value": "", "name": "-dsl1", "type": "str"}
            ],
            "snakemake": [
                {"default_value": 1, "name": "--cores", "type": "int"},
                {"default_value": "", "name": "--use-conda", "type": "str"}
            ]
        },
        "supported_filesystem_protocols": ["http", "https", "file", "s3"],
        "supported_wes_versions": ["sapporo-wes-1.1.0"],
        "system_state_counts": {},
        "tags": {
            "get_runs": True,
            "news_content": "",
            "registered_only_mode": False,
            "sapporo-version": "1.5.1",
            "wes-name": "sapporo",
            "workflow_attachment": True
        },
        "workflow_engine_versions": {
            "cromwell": "80",
            "cwltool": "3.1.20220628170238",
            "ep3 (experimental)": "v1.7.0",
            "nextflow": "22.04.4",
            "snakemake": "v7.8.3",
            "streamflow": "0.1.3",
            "toil (experimental)": "4.1.0"
        },
        "workflow_type_versions": {
            "CWL": {"workflow_type_version": ["v1.0", "v1.1", "v1.2"]},
            "NFL": {"workflow_type_version": ["1.0", "DSL2"]},
            "SMK": {"workflow_type_version": ["1.0"]},
            "StreamFlow": {"workflow_type_version": ["v1.0"]},
            "WDL": {"workflow_type_version": ["1.0"]}
        }
    }

    assert res.status_code == 200
    for key in expected:
        assert key in res_data
    assert res_data["tags"]["get_runs"] is True
    assert res_data["tags"]["registered_only_mode"] is False
    assert res_data["tags"]["workflow_attachment"] is True


def test_get_service_info_with_disables(delete_env_vars: None, tmpdir: Path) -> None:
    config = get_default_config(tmpdir)
    config.update({
        "get_runs": False,
        "registered_only_mode": True,
        "workflow_attachment": False
    })
    client = setup_test_client(config)
    res = client.get("/service-info")
    res_data = res.get_json()

    assert res.status_code == 200
    assert res_data["tags"]["get_runs"] is False
    assert res_data["tags"]["registered_only_mode"] is True
    assert res_data["tags"]["workflow_attachment"] is False
