# sapporo-service

[![DOI](https://zenodo.org/badge/220937589.svg)](https://zenodo.org/badge/latestdoi/220937589)
[![Apache License](https://img.shields.io/badge/license-Apache%202.0-orange.svg?style=flat&color=important)](http://www.apache.org/licenses/LICENSE-2.0)

<img src="https://raw.githubusercontent.com/sapporo-wes/sapporo/main/logo/sapporo-service.svg" width="400" style="display: block; margin-left: auto; margin-right: auto; margin-top: 30px; margin-bottom: 30px;" alt="sapporo-service logo">

**The sapporo-service underwent a major version up (2024/07/09). While we have maintained some level of compatibility, full backward compatibility is not guaranteed. For more details, please refer to the ["Differences Between Sapporo Service 2.x and 1.x"](https://github.com/sapporo-wes/sapporo-service?#differences-between-sapporo-service-2x-and-1x). The latest version of the previous major version is [1.7.1](https://github.com/sapporo-wes/sapporo-service/tree/1.7.1).**

The sapporo-service is a standard implementation conforming to the [Global Alliance for Genomics and Health](https://www.ga4gh.org) (GA4GH) [Workflow Execution Service](https://github.com/ga4gh/workflow-execution-service-schemas) (WES) API specification.

We have also extended the API specification. For more details, please refer to [`sapporo-wes-spec-2.0.0.yml`](./sapporo-wes-spec-2.0.0.yml) or [SwaggerUI - sapporo-wes-2.0.0](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/sapporo-wes-spec-2.0.0.yml).

The sapporo-service is compatible with the following workflow engines:

- [cwltool](https://github.com/common-workflow-language/cwltool)
- [nextflow](https://www.nextflow.io)
- [Toil (experimental)](https://toil.ucsc-cgl.org)
- [cromwell](https://github.com/broadinstitute/cromwell)
- [snakemake](https://snakemake.readthedocs.io/en/stable/)
- [ep3 (experimental)](https://github.com/tom-tan/ep3)
- [StreamFlow (experimental)](https://github.com/alpha-unito/streamflow)

## Installation and Startup

The sapporo-service is compatible with Python 3.8 and later versions.

You can install it using pip:

```bash
python3 -m pip install sapporo
```

To start the sapporo-service, run the following command:

```bash
sapporo
```

Afterwards, you can query `GET /service-info` or access `localhost:1122/docs` in your browser to view the API documentation.

### Using Docker

Alternatively, you can run the sapporo-service using Docker. If you want to use Docker-in-Docker (DinD), make sure to mount `docker.sock`, `/tmp`, and other necessary directories.

To start the sapporo-service using Docker, run the following command:

```bash
docker compose up -d
```

## Usage

You can view the help for the sapporo-service as follows:

```bash
sapporo --help
usage: sapporo [-h] [--host] [--port] [--debug] [--run-dir] [--service-info]
               [--executable-workflows] [--run-sh] [--url-prefix] [--base-url]
               [--allow-origin] [--auth-config] [--run-remove-older-than-days]

The sapporo-service is a standard implementation conforming to the Global
Alliance for Genomics and Health (GA4GH) Workflow Execution Service (WES) API
specification.

options:
  -h, --help            show this help message and exit
  --host                Host address for the service. (default: 127.0.0.1)
  --port                Port number for the service. (default: 1122)
  --debug               Enable debug mode.
  --run-dir             Directory where the runs are stored. (default: ./runs)
  --service-info        Path to the service_info.json file.
  --executable-workflows 
                        Path to the executable_workflows.json file.
  --run-sh              Path to the run.sh script.
  --url-prefix          URL prefix for the service endpoints. (default: '',
                        e.g., /sapporo/api)
  --base-url            Base URL for downloading the output files of the
                        executed runs. The files can be downloaded using the
                        format: {base_url}/runs/{run_id}/outputs/{path}.
                        (default: http://{host}:{port}{url_prefix})
  --allow-origin        Access-Control-Allow-Origin header value. (default: *)
  --auth-config         Path to the auth_config.json file.
  --run-remove-older-than-days 
                        Clean up run directories with a start time older than
                        the specified number of days.
```

### Run a Workflow

Since the sapporo-service is the Workflow Execution Service (WES), you can execute workflows by specifying the workflow document and workflow parameters (i.e., by calling `POST /runs`). However, this might be challenging at first. To help you get started, there are several examples of running workflows using `curl` in the `./tests/curl_example` directory. These examples should serve as useful references.

Additionally, it is recommended to review the API specifications. After starting the Sapporo service, you can access `http://localhost:1122/docs` to view the API specifications through the Swagger UI. This interface provides an easy way to understand the API and execute commands directly from the UI.

### Run Directory

The sapporo-service organizes all submitted workflows, workflow parameters, output files, and related data within a specific directory on the file system. This directory is known as the "run directory." To specify a different location for the run directory, use the startup argument `--run-dir` or set the environment variable `SAPPORO_RUN_DIR`.

The run directory structure is as follows:

```bash
$ tree run
.
└── 29
    └── 29109b85-7935-4e13-8773-9def402c7775
        ├── cmd.txt
        ├── end_time.txt
        ├── exe
        │   └── workflow_params.json
        ├── exit_code.txt
        ├── outputs
        │   ├── <output_file>
        ├── outputs.json 
        ├── run.pid
        ├── run_request.json
        ├── runtime_info.json
        ├── start_time.txt
        ├── state.txt
        ├── stderr.log
        ├── stdout.log
        ├── system_logs.json
        └── workflow_engine_params.txt
├── 2d
│   └── ...
└── 6b
    └── ...
└── sapporo.db
```

You can manage each run by physically deleting it using the `rm` command.

As of the sapporo-service 2.0.0, an SQLite database (`sapporo.db`) has been added inside the run directory. This database is used to speed up `GET /runs` calls. The master data remains within each run directory, and the database is updated every 30 minutes while sapporo is running. If you need the latest run status, use `GET /runs/{run_id}` instead of `GET /runs` or use `latest=true` query parameter with `GET /runs`.

### `run.sh`

The [`run.sh`](./sapporo/run.sh) script is used to abstract the workflow engine. When `POST /runs` is invoked, the sapporo-service forks the execution of `run.sh` after preparing the necessary files in the run directory. This allows you to adapt various workflow engines to WES by modifying `run.sh`.

By default, `run.sh` is located in the application directory of the sapporo-service. You can override this location using the startup argument `--run-sh` or the environment variable `SAPPORO_RUN_SH`.

### Executable Workflows

The sapporo-service can be configured to allow only specific workflows to be executed. This is managed using the `--executable-workflows` startup argument or the `SAPPORO_EXECUTABLE_WORKFLOWS` environment variable. These options specify the location of the `executable_workflows.json` file, which by default is located in the application directory of the sapporo-service.

The `executable_workflows.json` file manages the list of executable workflows in the following format:

```json
{
  "workflows": [
    "https://example.com/workflow.cwl"
  ]
}
```

The `executable_workflows.json` file contains a list of executable `workflow_url`s. If the array is empty, all workflows are allowed to execute. Each `workflow_url` must be a remote resource (http/https). When this list is defined, any `workflow_url` provided in a `POST /runs` request must be present in the list; otherwise, the request will return a 400 Bad Request.

You can retrieve the list of executable workflows via the API using the `GET /executable_workflows` endpoint.

### Download Output Files

The sapporo-service provides a feature to download output files and allows users to list and download files from the outputs directory of a run.

To list the files in the outputs directory, use the `GET /runs/{run_id}/outputs` endpoint. Additionally, you can download the entire outputs directory as a zip file by using the query parameter `?download=true` with the `GET /runs/{run_id}/outputs` endpoint.

To download a specific file in the outputs directory, use the `GET /runs/{run_id}/outputs/{path}` endpoint.

You can specify the base URL for downloading the output files using the `--base-url` startup argument or the `SAPPORO_BASE_URL` environment variable. The files can be downloaded using the format `{base_url}/runs/{run_id}/outputs/{path}`. By default, the base URL is `http://{host}:{port}{url_prefix}`. This feature is useful when using a reverse proxy such as Nginx or when a domain name is configured.

### Clean Up Run Directories

The sapporo-service provides a feature to clean up run directories that have a start time older than a specified number of days. This can be configured using the `--run-remove-older-than-days` startup argument or the `SAPPORO_RUN_REMOVE_OLDER_THAN_DAYS` environment variable.

By setting this option, the sapporo-service will automatically remove run directories that are older than the specified number of days, helping to manage disk space and maintain a clean working environment.

### Swagger UI

Since the sapporo-service is implemented using FastAPI, Swagger UI is available. After starting the sapporo-service, you can access Swagger UI by navigating to `http://localhost:1122/docs` in your browser. This interface allows you to review the API specifications and execute API requests directly from the browser.

### Generate RO-Crate

The sapporo-service generates an [RO-Crate](https://www.researchobject.org/ro-crate/) (i.e., `ro-crate-metadata.json`) after a run is executed. You can retrieve this RO-Crate using `GET /runs/{run_id}/ro-crate`. Additionally, you can download the entire RO-Crate package (i.e., all contents of the `run_dir`) as a zip file by using `GET /runs/{run_id}/ro-crate?download=true`. For more details, please refer to [`./tests/ro-crate`](./tests/ro-crate).

### Authentication

The sapporo-service supports authentication, configurable via the [`./sapporo/auth_config.json`](./sapporo/auth_config.json). By default, this configuration is as follows:

```json
{
  "auth_enabled": false,
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
```

This configuration file can be directly edited or relocated using the `--auth-config` startup argument or the `SAPPORO_AUTH_CONFIG` environment variable.

#### Configuration Fields

- `auth_enabled`: Determines if authentication is activated. If set to `true`, authentication is enabled.
- `idp_provider`: Specifies the type of authentication provider, supporting `sapporo` or `external`. This allows you to switch the authentication provider.
- `sapporo_auth_config`: Configuration for local authentication includes:
  - `secret_key`: Secret key for signing JWTs. Changing this key is highly recommended.
  - `expires_delta_hours`: The number of hours until the JWT expires. If null, the JWT never expires.
  - `users`: List of users eligible for authentication, specifying username and password.
- `external_config`: Configuration for external authentication includes:
  - `idp_url`: URL to access the identity provider's configuration. This should be accessible from Sapporo at `{idp_url}/.well-known/openid-configuration`.
  - `jwt_audience`: The expected audience claim in the JWT (e.g., `account`).
  - `client_mode`: Mode of the client, either `confidential` or `public`.
  - `client_id`: The client ID for the external authentication provider. This is used when `client_mode` is `confidential`.
  - `client_secret`: The client secret for the external authentication provider. This is used when `client_mode` is `confidential`.

From this configuration, there are two authentication modes: `sapporo` and `external`. When the mode is set to `sapporo`, Sapporo acts as an Identity Provider (IdP), issuing JWTs and handling authentication. In contrast, when the mode is set to `external`, authentication is delegated to an external IdP (e.g., Keycloak). In this scenario, Sapporo verifies the JWTs, but the JWTs are issued by the external IdP.

Each mode is explained in more detail below.

#### Authentication Endpoints

When authentication is enabled, the following endpoints require authentication headers:

- `GET /runs`
- `POST /runs`
- `GET /runs/{run_id}`
- `POST /runs/{run_id}/cancel`
- `GET /runs/{run_id}/status`
- `GET /runs/{run_id}/data`
- `GET /runs/{run_id}/outputs`
- `GET /runs/{run_id}/outputs/{path:path}`
- `GET /runs/{run_id}/ro-crate`
- `DELETE /runs/{run_id}`

Each run is associated with a `username`, ensuring that only the user who created a run can access details like `GET /runs/{run_id}`.

#### Authentication: `sapporo` mode

For `sapporo` mode authentication, configure `auth_config.json` as shown:

```json
{
  "auth_enabled": true,
  "idp_provider": "sapporo",
  "sapporo_auth_config": {
    "secret_key": "new_secret_key",
    "expires_delta_hours": 24,
    "users": [
      {
        "username": "user1",
        "password": "password1"
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
```

Start the sapporo-service with this configuration. You will be able to access the `GET /service-info` endpoint, but endpoints like `GET /runs` will require authentication:

```bash
# Start sapporo-service
sapporo

# GET /service-info
$ curl -X GET localhost:1122/service-info
...
"auth_instructions_url": "<https://github.com/sapporo-wes/sapporo-service/blob/main/README.md#authentication>",

$ curl -X GET localhost:1122/runs
{
  "msg": "Not authenticated",
  "status_code": 401
}
```

To authenticate, obtain a JWT via `POST /token`:

```bash
# Generate JWT for authentication
$ curl -s -X POST \
    -H "Content-Type: multipart/form-data" \
    -F "username=user1" \
    -F "password=password1" \
    localhost:1122/token
{
  "access_token":"<generated_jwt>",
  "token_type":"bearer"
}

$ TOKEN=$(curl -s -X POST \
    -H "Content-Type: multipart/form-data" \
    -F "username=user1" \
    -F "password=password1" \
    localhost:1122/token | jq -r '.access_token')

# Check the JWT
$ curl -X GET \
    -H "Authorization: Bearer $TOKEN" \
    localhost:1122/me
{"username":"user1"}
```

With the obtained JWT, you can access endpoints like `GET /runs`:

```bash
$ curl -X GET -H "Authorization: Bearer $TOKEN" localhost:1122/runs
{
  "runs": []
}
```

#### Authentication: `external` mode

In `external` mode, the sapporo-service can integrate with an external IdP such as Keycloak. In this case, user information must be registered with the IdP. The IdP issues JWTs, and the sapporo-service verifies these JWTs.

As an example, a ***./compose.keycloak.dev.yml*** file is provided for Keycloak. By using this file, you can start Keycloak and configure the necessary Realm and Client settings to integrate with the sapporo-service.

After obtaining a JWT from the IdP, include the `Authorization: Bearer` header in your requests to the authenticated endpoints.

## Development

To start the development environment, follow these steps:

```bash
docker compose -f compose.dev.yml up -d --build
docker compose -f compose.dev.yml exec app bash
# inside the container
sapporo --debug
```

To run the lint, format, and test commands, use the following:

```bash
# List and Format
pylint ./sapporo
mypy ./sapporo
isort ./sapporo

# Test
pytest
```

## Differences Between Sapporo Service 2.x and 1.x

- Changed from Flask to FastAPI.
- Updated the base GA4GH WES from WES 1.0.0 to WES 1.1.0.
- Reorganized authentication and enabled switching of authentication methods.
- Added an SQLite database directly under the run directory to speed up high-load endpoints like `GET /runs`.
- Organized the Python and Docker toolchain.
- Adjusted the `run_only_registered_only_mode` specification to manage simple lists of `workflow_url`s in `executable_workflows.json`.
- Fully supported the clean-up run directories feature.
- For detailed API specifications, refer to [`sapporo-wes-spec-2.0.0.yml`](./sapporo-wes-spec-2.0.0.yml) or [SwaggerUI - sapporo-wes-2.0.0](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/sapporo-wes-spec-2.0.0.yml).

## Adding New Workflow Engines to the Sapporo-service

The sapporo-service calls each workflow engine through the [`run.sh`](./sapporo/run.sh) script. Therefore, by editing `run.sh`, you can easily add new workflow engines or modify the behavior of existing ones. For an example of adding a new workflow engine, refer to the pull request that includes the addition of the `Streamflow` workflow engine: <https://github.com/sapporo-wes/sapporo-service/pull/29>

## License

This project is licensed under the [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) license. See the [LICENSE](./LICENSE) file for details.
