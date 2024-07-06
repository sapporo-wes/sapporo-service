# pylint: disable=C0415, W0613, W0621
import json

import pytest

from .conftest import anyhow_get_test_client


@pytest.fixture(autouse=True)
def clear_create_service_info_cache():  # type: ignore
    from sapporo.factory import create_service_info
    create_service_info.cache_clear()


def test_get_service_info(mocker, tmpdir):  # type: ignore
    client = anyhow_get_test_client(None, mocker, tmpdir)
    response = client.get("/service-info")
    assert response.status_code == 200


def test_get_service_info_from_file(mocker, tmpdir):  # type: ignore
    from sapporo.config import AppConfig

    service_info = tmpdir.joinpath("service-info.json")
    with service_info.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "test-sapporo-service"}))
    client = anyhow_get_test_client(AppConfig(service_info=service_info), mocker, tmpdir)

    response = client.get("/service-info")
    assert response.status_code == 200

    data = response.json()
    print(data)
    assert "id" in data
    assert data["id"] == "test-sapporo-service"
