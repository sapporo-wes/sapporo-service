# pylint: disable=C0415, W0613, W0621

import json

from .conftest import anyhow_get_test_client


def test_get_service_info(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = client.get("/service-info")
    assert response.status_code == 200


def test_get_service_info_from_file(mocker, tmpdir):  # type: ignore
    from sapporo.config import AppConfig

    service_info = tmpdir.joinpath("service-info.json")
    with service_info.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "test-sapporo-service"}))
    app_config = AppConfig(service_info=service_info)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    response = client.get("/service-info")
    assert response.status_code == 200

    data = response.json()
    assert "id" in data
    assert data["id"] == "test-sapporo-service"
