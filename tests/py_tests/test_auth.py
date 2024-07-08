# pylint: disable=C0415, W0613, W0621

"""\
I wanted to write tests for auth, but in many cases, it is difficult to write tests with pytest
because it requires integration with external IdP (e.g., keycloak).
"""


import json

from .conftest import anyhow_get_test_client, post_run, wait_for_run
from .test_run_cwltool import remote_wf_run_request


def default_auth_config():  # type: ignore
    return {
        "auth_enabled": False,
        "idp_provider": "sapporo",
        "sapporo_auth_config": {
            "secret_key": "sapporo_secret_key_please_change_this",
            "expires_delta_hours": 24,
            "users": [
                {
                    "username": "sapporo-dev-user",
                    "password": "sapporo-dev-password"
                }
            ]
        },
        "external_config": {
            "idp_url": "http://sapporo-keycloak-dev:8080/realms/sapporo-dev",
            "jwt_audience": "account",
            "client_mode": "public",
            "client_id": "sapporo-service-dev",
            "client_secret": "example-client-secret"
        }
    }


def test_no_auth_get_runs(mocker, tmpdir):  # type: ignore
    from sapporo.config import AppConfig

    auth_config = tmpdir.joinpath("auth_config.json")
    with auth_config.open("w", encoding="utf-8") as f:
        f.write(json.dumps(default_auth_config()))  # type: ignore
    app_config = AppConfig(auth_config=auth_config)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    response = client.get("/runs")
    assert response.status_code == 200


def test_no_auth_post_runs(mocker, tmpdir):  # type: ignore
    from sapporo.config import AppConfig

    auth_config = tmpdir.joinpath("auth_config.json")
    with auth_config.open("w", encoding="utf-8") as f:
        f.write(json.dumps(default_auth_config()))  # type: ignore
    app_config = AppConfig(auth_config=auth_config)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    response = post_run(client, **remote_wf_run_request)  # type: ignore
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]
    wait_for_run(client, run_id)
