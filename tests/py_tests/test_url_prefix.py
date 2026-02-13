from .conftest import anyhow_get_test_client


def test_url_prefix(mocker, tmpdir):  # type: ignore[no-untyped-def]
    from sapporo.config import AppConfig

    url_prefix = "/api"

    app_config = AppConfig(url_prefix=url_prefix)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    response = client.get(f"{url_prefix}/service-info")
    assert response.status_code == 200
