# coding: utf-8
# pylint: disable=unused-argument
import pytest
from cwl_inputs_parser.utils import download_file
from flask.testing import FlaskClient

WORKFLOW_LOCATIONS = {
    "CWL": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimming_and_qc_remote.cwl",
    "WDL": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cromwell/dockstore-tool-bamstats/Dockstore.wdl",
    "NFL": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/nextflow/file_input.nf",
    "SMK": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/snakemake/Snakefile"
}


@pytest.mark.parametrize("workflow_type,workflow_type_version", [("CWL", "v1.0"), ("WDL", "1.0"), ("NFL", "1.0"), ("SMK", "1.0")])
def test_parse_workflow_type_version(delete_env_vars: None, test_client: FlaskClient, workflow_type: str, workflow_type_version: str) -> None:  # type: ignore
    res = test_client.post("/parse-workflow",
                           data={"workflow_location": WORKFLOW_LOCATIONS[workflow_type]},
                           content_type="multipart/form-data")
    res_data = res.get_json()
    assert res_data["inputs"] is None
    assert res_data["workflow_type"] == workflow_type
    assert res_data["workflow_type_version"] == workflow_type_version


def test_parse_cwl_type_version_by_content(delete_env_vars: None, test_client: FlaskClient) -> None:  # type: ignore
    res = test_client.post("/parse-workflow",
                           data={
                               "workflow_content": download_file(WORKFLOW_LOCATIONS["CWL"]),
                           },
                           content_type="multipart/form-data")
    res_data = res.get_json()
    assert res_data["inputs"] is None
    assert res_data["workflow_type"] == "CWL"
    assert res_data["workflow_type_version"] == "v1.0"


def test_parse_cwl_inputs(delete_env_vars: None, test_client: FlaskClient) -> None:  # type: ignore
    res = test_client.post("/parse-workflow",
                           data={"workflow_location": WORKFLOW_LOCATIONS["CWL"], "types_of_parsing": ["inputs"]},
                           content_type="multipart/form-data")
    res_data = res.get_json()
    assert res_data["inputs"] is not None
    assert res_data["workflow_type"] == "CWL"
    assert res_data["workflow_type_version"] == "v1.0"


def test_parse_cwl_make_template(delete_env_vars: None, test_client: FlaskClient) -> None:  # type: ignore
    res = test_client.post("/parse-workflow",
                           data={"workflow_location": WORKFLOW_LOCATIONS["CWL"], "types_of_parsing": ["make_template"]},
                           content_type="multipart/form-data")
    res_data = res.get_json()
    assert res_data["inputs"] is not None
    assert isinstance(res_data["inputs"], str)
    assert res_data["workflow_type"] == "CWL"
    assert res_data["workflow_type_version"] == "v1.0"
