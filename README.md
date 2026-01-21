# sapporo-service

[![DOI](https://zenodo.org/badge/220937589.svg)](https://zenodo.org/badge/latestdoi/220937589)
[![Apache License](https://img.shields.io/badge/license-Apache%202.0-orange.svg?style=flat&color=important)](http://www.apache.org/licenses/LICENSE-2.0)

<img src="https://raw.githubusercontent.com/sapporo-wes/sapporo/main/logo/sapporo-service.svg" width="400" style="display: block; margin-left: auto; margin-right: auto; margin-top: 30px; margin-bottom: 30px;" alt="sapporo-service logo">

The sapporo-service is a standard implementation conforming to the [Global Alliance for Genomics and Health](https://www.ga4gh.org) (GA4GH) [Workflow Execution Service](https://github.com/ga4gh/workflow-execution-service-schemas) (WES) API specification.

We have also extended the API specification. For more details, please refer to [`sapporo-wes-spec-2.0.0.yml`](./sapporo-wes-spec-2.0.0.yml) or [SwaggerUI - sapporo-wes-2.0.0](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/sapporo-wes-spec-2.0.0.yml).

## Installation and Startup

The sapporo-service requires Python 3.8 or later.

Install using pip:

```bash
python3 -m pip install sapporo
```

Start the service:

```bash
sapporo
```

After startup, access `localhost:1122/docs` to view the API documentation, or query `GET /service-info` to verify the service is running.

### Using Docker

You can also run the sapporo-service using Docker. For Docker-in-Docker (DinD) setups, mount `docker.sock`, `/tmp`, and other necessary directories.

```bash
docker compose up -d
```

## Supported Workflow Engines

The sapporo-service supports the following workflow engines:

- [cwltool](https://github.com/common-workflow-language/cwltool)
- [nextflow](https://www.nextflow.io)
- [Toil (experimental)](https://toil.ucsc-cgl.org)
- [cromwell](https://github.com/broadinstitute/cromwell)
- [snakemake](https://snakemake.readthedocs.io/en/stable/)
- [ep3 (experimental)](https://github.com/tom-tan/ep3)
- [StreamFlow (experimental)](https://github.com/alpha-unito/streamflow)

## Usage

View available options:

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

Execute workflows by calling `POST /runs` with the workflow document and parameters. See the `./tests/curl_example` directory for example requests using `curl`.

After starting the service, access `http://localhost:1122/docs` to view API specifications through Swagger UI and execute requests directly from the browser.

### Run Directory

The sapporo-service stores all workflow data in a "run directory" on the filesystem. Configure the location using `--run-dir` or the `SAPPORO_RUN_DIR` environment variable.

Structure:

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
        │   └── <output_file>
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
└── sapporo.db
```

Runs can be deleted by removing their directories with `rm`.

As of version 2.0.0, an SQLite database (`sapporo.db`) indexes runs for faster `GET /runs` queries. The database is updated every 30 minutes. For real-time run status, use `GET /runs/{run_id}` or add `latest=true` to `GET /runs`.

### `run.sh`

The [`run.sh`](./sapporo/run.sh) script abstracts workflow engine execution. When `POST /runs` is called, the service forks `run.sh` after preparing run directory files. Modify this script to add or customize workflow engine support.

Override the default location using `--run-sh` or `SAPPORO_RUN_SH`.

### Executable Workflows

Restrict which workflows can be executed using `--executable-workflows` or `SAPPORO_EXECUTABLE_WORKFLOWS`.

Format:

```json
{
  "workflows": [
    "https://example.com/workflow.cwl"
  ]
}
```

An empty array allows all workflows. Each URL must be a remote resource (http/https). Any `workflow_url` in `POST /runs` must match this list or the request returns 400 Bad Request.

Query available workflows via `GET /executable_workflows`.

### Download Output Files

List output files using `GET /runs/{run_id}/outputs`. Download all outputs as a zip file with `?download=true`.

Download specific files using `GET /runs/{run_id}/outputs/{path}`.

Configure the base URL for downloads using `--base-url` or `SAPPORO_BASE_URL`. Files are accessible at `{base_url}/runs/{run_id}/outputs/{path}`.

### Clean Up Run Directories

Automatically remove old run directories using `--run-remove-older-than-days` or `SAPPORO_RUN_REMOVE_OLDER_THAN_DAYS`.

### Swagger UI

Access Swagger UI at `http://localhost:1122/docs` to explore API specifications and execute requests interactively.

### Generate RO-Crate

The sapporo-service generates [RO-Crate](https://www.researchobject.org/ro-crate/) metadata (`ro-crate-metadata.json`) after each run. Retrieve it using `GET /runs/{run_id}/ro-crate`. Download the complete RO-Crate package as a zip file with `?download=true`. See [`./tests/ro-crate`](./tests/ro-crate) for details.

## Authentication

Configure authentication via [`./sapporo/auth_config.json`](./sapporo/auth_config.json):

```json
{
  "auth_enabled": true,
  "idp_provider": "sapporo",
  "sapporo_auth_config": {
    "secret_key": "your_secure_secret_key_here",
    "expires_delta_hours": 24,
    "users": [
      {
        "username": "user1",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$..."
      }
    ]
  },
  "external_config": {
    "idp_url": "https://keycloak.example.com/realms/your-realm",
    "jwt_audience": "account",
    "client_mode": "public",
    "client_id": "sapporo-client",
    "client_secret": "client-secret-here"
  }
}
```

Override the location using `--auth-config` or `SAPPORO_AUTH_CONFIG`.

### Configuration Fields

- `auth_enabled`: Enable/disable authentication
- `idp_provider`: `sapporo` (local) or `external` (IdP like Keycloak)
- `sapporo_auth_config`:
  - `secret_key`: JWT signing key (must be strong, see [Security](#security))
  - `expires_delta_hours`: JWT expiration time in hours (default: 24, max: 168)
  - `users`: List of users with `username` and `password_hash`
- `external_config`:
  - `idp_url`: External IdP URL (must use HTTPS in production)
  - `jwt_audience`: Expected JWT audience claim
  - `client_mode`: `confidential` or `public`
  - `client_id`/`client_secret`: OAuth2 credentials for confidential mode

### Authentication Endpoints

When authentication is enabled, the following endpoints require a valid JWT token:

- `GET /service-info` (optional: provides user-specific counts when authenticated)
- `GET /runs`
- `POST /runs`
- `GET /runs/{run_id}`
- `POST /runs/{run_id}/cancel`
- `GET /runs/{run_id}/status`
- `GET /runs/{run_id}/outputs`
- `GET /runs/{run_id}/outputs/{path:path}`
- `GET /runs/{run_id}/ro-crate`
- `DELETE /runs/{run_id}`

Each run is associated with a username, ensuring users can only access their own runs.

### Authentication: `sapporo` mode

For local authentication:

```bash
# Start sapporo-service
sapporo

# Get JWT token
TOKEN=$(curl -s -X POST \
    -H "Content-Type: multipart/form-data" \
    -F "username=user1" \
    -F "password=yourpassword" \
    localhost:1122/token | jq -r '.access_token')

# Verify token
curl -X GET -H "Authorization: Bearer $TOKEN" localhost:1122/me

# Access protected endpoints
curl -X GET -H "Authorization: Bearer $TOKEN" localhost:1122/runs
```

### Authentication: `external` mode

In external mode, integrate with an IdP like Keycloak. Users authenticate with the IdP, which issues JWTs that the sapporo-service verifies.

See `./compose.keycloak.dev.yml` for a Keycloak development setup example.

## Security

### Password Hashing

All passwords are stored as Argon2 hashes. Generate password hashes using the CLI:

```bash
python -m sapporo.cli hash-password
# Follow the prompts to enter and confirm your password
# Output: Password hash: $argon2id$v=19$m=65536,t=3,p=4$...
```

Or programmatically (not recommended for interactive use):

```bash
python -m sapporo.cli hash-password --password "your_password"
```

### Secret Key Generation

Generate a cryptographically secure secret key:

```bash
python -m sapporo.cli generate-secret
# Output: Secret key: <44-character secure random string>
```

**Important:** In production mode (non-debug), weak secret keys are rejected. Always use a generated secret key in production deployments.

### HTTPS for External IdP

When using external identity providers, HTTPS is required by default. This prevents token interception during authentication flows.

To allow HTTP connections during development (not recommended for production):

```bash
export SAPPORO_ALLOW_INSECURE_IDP=true
```

## Development

Start the development environment:

```bash
docker compose -f compose.dev.yml up -d --build
docker compose -f compose.dev.yml exec app bash
# Inside the container
sapporo --debug
```

Run lint and tests:

```bash
# Lint and format
pylint ./sapporo
mypy ./sapporo
isort ./sapporo

# Test
pytest
```

## Differences Between Sapporo Service 2.x and 1.x

- Changed from Flask to FastAPI
- Updated base GA4GH WES from 1.0.0 to 1.1.0
- Reorganized authentication with switchable methods
- Added SQLite database for faster `GET /runs` queries
- Organized Python and Docker toolchain
- Simplified `executable_workflows.json` to a list of `workflow_url`s
- Full support for automatic run directory cleanup
- See [`sapporo-wes-spec-2.0.0.yml`](./sapporo-wes-spec-2.0.0.yml) for detailed API specifications

## Adding New Workflow Engines to the Sapporo-service

The sapporo-service invokes workflow engines through [`run.sh`](./sapporo/run.sh). Edit this script to add or customize workflow engines. For an example, see the [StreamFlow addition PR](https://github.com/sapporo-wes/sapporo-service/pull/29).

## License

This project is licensed under the [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) license. See the [LICENSE](./LICENSE) file for details.
