# sapporo-service

[![pytest](https://github.com/sapporo-wes/sapporo-service/actions/workflows/pytest.yml/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions/workflows/pytest.yml)
[![flake8](https://github.com/sapporo-wes/sapporo-service/actions/workflows/flake8.yml/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions/workflows/flake8.yml)
[![isort](https://github.com/sapporo-wes/sapporo-service/actions/workflows/isort.yml/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions/workflows/isort.yml)
[![mypy](https://github.com/sapporo-wes/sapporo-service/actions/workflows/mypy.yml/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions/workflows/mypy.yml)
[![DOI](https://zenodo.org/badge/220937589.svg)](https://zenodo.org/badge/latestdoi/220937589)
[![Apache License](https://img.shields.io/badge/license-Apache%202.0-orange.svg?style=flat&color=important)](http://www.apache.org/licenses/LICENSE-2.0)

<img src="https://raw.githubusercontent.com/sapporo-wes/sapporo/main/logo/sapporo-service.svg" width="400" style="display: block; margin-left: auto; margin-right: auto; margin-top: 30px; margin-bottom: 30px;" alt="sapporo-service logo">

The sapporo-service is a standard implementation conforming to the [Global Alliance for Genomics and Health](https://www.ga4gh.org) (GA4GH) [Workflow Execution Service](https://github.com/ga4gh/workflow-execution-service-schemas) (WES) API specification.

We have also extended the API specification.
For more details, please refer to [`./sapporo-wes-1-1-0-openapi-spec.yml`](./sapporo-wes-1-1-0-openapi-spec.yml) for more details.

One of the key features of the sapporo-service is its ability to abstract workflow engines, making it easy to adapt various workflow engines to the WES standard.
Currently, we have verified compatibility with the following workflow engines:

- [cwltool](https://github.com/common-workflow-language/cwltool)
- [nextflow](https://www.nextflow.io)
- [Toil (experimental)](https://toil.ucsc-cgl.org)
- [cromwell](https://github.com/broadinstitute/cromwell)
- [snakemake](https://snakemake.readthedocs.io/en/stable/)
- [ep3 (experimental)](https://github.com/tom-tan/ep3)
- [StreamFlow (experimental)](https://github.com/alpha-unito/streamflow)

Another unique feature of the sapporo-service is a mode that permits only workflows registered by the system administrator to be executed.
This feature is particularly beneficial when setting up a WES in a shared HPC environment.

## Installation and Startup

The sapporo-service is compatible with Python 3.8 or later versions.

You can install it using pip:

```bash
pip3 install sapporo
```

To start the sapporo-service, run the following command:

```bash
sapporo
```

### Using Docker

Alternatively, you can run the sapporo-service using Docker.
If you want to use Docker-in-Docker (DinD), make sure to mount `docker.sock`, `/tmp`, and other necessary directories.

To start the sapporo-service using Docker, run the following command:

```bash
docker compose up -d
```

## Usage

You can view the help for the sapporo-service as follows:

```bash
$ sapporo --help
usage: sapporo [-h] [--host] [-p] [--debug] [-r] [--disable-get-runs]
               [--disable-workflow-attachment] [--run-only-registered-workflows]
               [--service-info] [--executable-workflows] [--run-sh]
               [--url-prefix] [--auth-config]

This is an implementation of a GA4GH workflow execution service that can easily
support various workflow runners.

optional arguments:
  -h, --help            show this help message and exit
  --host                Specify the host address for Flask. (default: 127.0.0.1)
  -p , --port           Specify the port for Flask. (default: 1122)
  --debug               Enable Flask's debug mode.
  -r , --run-dir        Specify the run directory. (default: ./run)
  --disable-get-runs    Disable the `GET /runs` endpoint.
  --disable-workflow-attachment
                        Disable the `workflow_attachment` feature on the `Post
                        /runs` endpoint.
  --run-only-registered-workflows
                        Only run registered workflows. Check the registered
                        workflows using `GET /executable-workflows`, and specify
                        the `workflow_name` in the `POST /run` request.
  --service-info        Specify the `service-info.json` file. The
                        `supported_wes_versions` and `system_state_counts` will
                        be overwritten by the application.
  --executable-workflows
                        Specify the `executable-workflows.json` file.
  --run-sh              Specify the `run.sh` file.
  --url-prefix          Specify the prefix of the URL (e.g., --url-prefix /foo
                        will result in /foo/service-info).
  --auth-config         Specify the `auth-config.json` file.
```

### Operating Mode

The sapporo-service can be started in one of the following two modes:

- Standard WES mode (Default)
- Execute only registered workflows mode

You can switch between these modes using the `--run-only-registered-workflows` startup argument or by setting the `SAPPORO_ONLY_REGISTERED_WORKFLOWS` environment variable to `True` or `False`.
Note that startup arguments take precedence over environment variables.

#### Standard WES Mode

In this mode, the sapporo-service conforms to the standard WES API specification.

#### Execute Only Registered Workflows Mode

In this mode, the sapporo-service only allows workflows registered by the system administrator to be executed.

The key changes in this mode are:

- `GET /executable_workflows` returns the list of executable workflows.
- `POST /runs`, use `workflow_name` instead of `workflow_url`.

The list of executable workflows is managed in [`executable_workflows.json`](./sapporo/executable_workflows.json).
By default, this file is located in the application directory of the sapporo-service.
However, you can override it using the startup argument `--executable-workflows` or the environment variable `SAPPORO_EXECUTABLE_WORKFLOWS`.

### Run Directory

The sapporo-service organizes all submitted workflows, workflow parameters, output files, and related data within a specific directory on the file system.
This directory, known as the "run directory".
To specify a different location for the run directory, use the startup argument `--run-dir` or set the environment variable `SAPPORO_RUN_DIR`.

The run dir structure is as follows:

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
        ├── start_time.txt
        ├── state.txt
        ├── stderr.log
        ├── stdout.log
        └── workflow_engine_params.txt
├── 2d
│   └── ...
└── 6b
    └── ...
```

You can manage each run by physically deleting it using the `rm` command.

Executing `POST /runs` can be quite complex.
For your convenience, we've provided examples using `curl` in the [`./tests/curl_example`](./tests/curl_example) directory.
Please refer to these examples as a guide.

### `run.sh`

The [`run.sh`](./sapporo/run.sh) script is used to abstract the workflow engine.
When `POST /runs` is invoked, the sapporo-service forks the execution of `run.sh` after preparing the necessary files in the run directory.
This allows you to adapt various workflow engines to WES by modifying `run.sh`.

By default, `run.sh` is located in the application directory of the sapporo-service.
You can override this location using the startup argument `--run-sh` or the environment variable `SAPPORO_RUN_SH`.

### Other Startup Arguments

You can modify the host and port used by the application using the startup arguments `--host` and `--port` or the environment variables `SAPPORO_HOST` and `SAPPORO_PORT`.

The following three startup arguments and corresponding environment variables can be used to limit the WES:

- `--disable-get-runs` / `SAPPORO_GET_RUNS`: Disables `GET /runs`. This can be useful when using WES with an unspecified number of users, as it prevents users from viewing or cancelling other users' runs by knowing the run_id.
- `--disable-workflow-attachment` / `SAPPORO_WORKFLOW_ATTACHMENT`: Disables the `workflow_attachment` field in `POST /runs`. This field is used to attach files for executing workflows, and disabling it can address security concerns.
- `--url-prefix` / `SAPPORO_URL_PREFIX`: Sets the URL prefix. For example, if `--url-prefix /foo/bar` is set, `GET /service-info` becomes `GET /foo/bar/service-info`.

The response content of `GET /service-info` is managed in [`service-info.json`](./sapporo/service-info.json).
By default, this file is located in the application directory of the sapporo-service.
You can override this location using the startup argument `--service-info` or the environment variable `SAPPORO_SERVICE_INFO`.

### Generate Download Link

The sapporo-service allows you to generate download links for files and directories located under the `run_dir`.

For more details, please refer to the `GetData` section in [`./sapporo-wes-1-1-0-openapi-spec.yml`](./sapporo-wes-1-1-0-openapi-spec.yml).

### Parse Workflow

The sapporo-service offers a feature to inspect the type, version, and inputs of a workflow document.

For more details, please refer to the `ParseWorkflow` section in [`./sapporo-wes-1-1-0-openapi-spec.yml`](./sapporo-wes-1-1-0-openapi-spec.yml).

### Generate RO-Crate

Upon completion of workflow execution, the sapporo-service generates an RO-Crate from the `run_dir`, which is saved as `ro-crate-metadata.json` within the same directory. You can download the RO-Crate using the `GET /runs/{run_id}/ro-crate/data/ro-crate-metadata.json` endpoint.

Additionally, you can generate an RO-Crate from the `run_dir` as follows:

```bash
# Inside the Sapporo run_dir
$ ls
cmd.txt                     run.sh                      state.txt
exe/                        run_request.json            stderr.log
executable_workflows.json   sapporo_config.json         stdout.log
outputs/                    service_info.json           workflow_engine_params.txt
run.pid                     start_time.txt              yevis-metadata.yml

# Execute the sapporo/ro_crate.py script
$ docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v $PWD:$PWD -w $PWD ghcr.io/sapporo-wes/sapporo-service:latest python3 /app/sapporo/ro_crate.py $PWD
```

For more information on RO-Crate, please also refer to [`./tests/ro-crate`](./tests/ro-crate).

### Authentication

The sapporo-service supports authentication using JWT.
The configuration for this authentication is managed through [`./sapporo/auth_config.json`](./sapporo/auth_config.json) file.
By default, the file is set up as follows:

```json
{
  "auth_enabled": false,
  "jwt_secret_key": "spr_secret_key_please_change_this",
  "users": [
    {
      "username": "spr_test_user",
      "password": "spr_test_password"
    }
  ]
}
```

You can edit this file directly, or, you can change its location using the startup argument `--auth-config` or the environment variable `SAPPORO_AUTH_CONFIG`.

The file contains the following fields:

- `auth_enabled`: Determines whether JWT authentication is enabled. If set to `true`, JWT authentication is activated.
- `jwt_secret_key`: The secret key used for signing the JWT. It is strongly recommended to change this value.
- `users`: A list of users who will perform JWT authentication. Specify `username` and `password`.

When JWT authentication is enabled, the following endpoints require authentication:

- `GET /runs`
- `POST /runs`
- `GET /runs/{run_id}`
- `POST /runs/{run_id}/cancel`
- `GET /runs/{run_id}/status`
- `GET /runs/{run_id}/data`

Additionally, each run is associated with a `username`, so that, for example, only the user who created the run can access `GET /runs/{run_id}`.

Let's take a look at how to use JWT authentication.
First, edit the `auth-config.json` as follows:

```json
{
  "auth_enabled": true,
  "jwt_secret_key": "spr_secret_key_please_change_this",
  "users": [
    {
      "username": "spr_test_user1",
      "password": "spr_test_password1"
    },
    {
      "username": "spr_test_user2",
      "password": "spr_test_password2"
    }
  ]
}
```

With this configuration, if you start the sapporo-service, `GET /service-info` will return a result, but `GET /runs` will require authentication.

```bash
# Start sapporo-service
$ sapporo

# GET /service-info
$ curl -X GET localhost:1122/service-info
{
  "auth_instructions_url": "https://github.com/sapporo-wes/sapporo-service",
  "contact_info_url": "https://github.com/sapporo-wes/sapporo-service",
...

# GET /runs
$ curl -X GET localhost:1122/runs
{
  "msg": "Missing Authorization Header",
  "status": 401
}
```

Here, you can generate a JWT required for authentication by sending a `POST /auth` request with `username` and `password` as follows:

```bash
$ curl -X POST \
    -H "Content-Type: application/json" \
    -d '{"username":"spr_test_user1", "password":"spr_test_password1"}' \
    localhost:1122/auth
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTcwNjQyODY2MCwianRpIjoiY2I5ZTU1MDgtN2RlNy00Y2EzLWE4NjYtN2ZlYmRmYTg4YWQ0IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6InNwcl90ZXN0X3VzZXIxIiwibmJmIjoxNzA2NDI4NjYwLCJjc3JmIjoiZjdlZjNhZmYtMTVlZS00OTc2LTkxYzYtOTU2ZDZjZTVjYmQ5IiwiZXhwIjoxNzA2NDI5NTYwfQ.zyD7Ru72eD_9mJj548DS-qDk8Y5yan-rNbklWmfvcEs"
}
```

If you attach this generated JWT to the Authorization header and send it to `GET /runs`, the authentication will pass.

```bash
$ TOKEN1=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{"username":"spr_test_user1", "password":"spr_test_password1"}' \
    localhost:1122/auth | jq -r '.access_token')

$ curl -X GET -H "Authorization: Bearer $TOKEN1" localhost:1122/runs
{
  "runs": []
}
```

Let's also confirm that User2 cannot access the run executed by User1.

```bash
$ TOKEN1=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{"username":"spr_test_user1", "password":"spr_test_password1"}' \
    localhost:1122/auth | jq -r '.access_token')
$ TOKEN2=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{"username":"spr_test_user2", "password":"spr_test_password2"}' \
    localhost:1122/auth | jq -r '.access_token')

# Execute a run with User1
# Please refer to ./tests/curl_example/cwltool_remote_workflow.sh for example
# Run ID: af95fd09-8406-4f2c-9280-bca900e07289

# GET /runs with User1
$ curl -X GET -H "Authorization: Bearer $TOKEN1" localhost:1122/runs
{
  "runs": [
    {
      "run_id": "af95fd09-8406-4f2c-9280-bca900e07289",
      "state": "COMPLETE"
    }
  ]
}

# GET /runs/{run_id} with User1
$ curl -X GET -H "Authorization: Bearer $TOKEN1" localhost:1122/runs/af95fd09-8406-4f2c-9280-bca900e07289
{
  "outputs": [
    {
      ...

# GET /runs with User2
$ curl -X GET -H "Authorization: Bearer $TOKEN2" localhost:1122/runs
{
  "runs": []
}

# GET /runs/{run_id} with User2
$ curl -X GET -H "Authorization: Bearer $TOKEN2" localhost:1122/runs/af95fd09-8406-4f2c-9280-bca900e07289
{
  "msg": "You don't have permission to access this run.",
  "status_code": 403
}
```

## Development

To start the development environment, follow these steps:

```bash
$ docker compose -f compose.dev.yml up -d --build
$ docker compose -f compose.dev.yml exec app bash
# inside container
$ sapporo
```

We utilize [flake8](https://pypi.org/project/flake8/), [isort](https://github.com/timothycrosley/isort), and [mypy](http://mypy-lang.org) for linting and style checking.

```bash
bash ./tests/lint_and_style_check/flake8.sh
bash ./tests/lint_and_style_check/isort.sh
bash ./tests/lint_and_style_check/mypy.sh

bash ./tests/lint_and_style_check/run_all.sh
```

For testing, we use [pytest](https://docs.pytest.org/en/latest/).

```bash
pytest .
```

## Adding New Workflow Engines to Sapporo Service

Take a look at the [`run.sh`](./sapporo/run.sh) script, which is invoked from Python. This shell script receives a request with a Workflow Engine such as cwltool and triggers the `run_cwltool` bash function.

This function executes a Bash Shell command to start a Docker container for the Workflow Engine and monitors its exit status. For a comprehensive example, please refer to this pull request: <https://github.com/sapporo-wes/sapporo-service/pull/29>

## License

This project is licensed under [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0). See the [LICENSE](./LICENSE) file for details.

## Notice

Please note that this repository is participating in a study into sustainability of open source projects. Data will be gathered about this repository for approximately the next 12 months, starting from 2021-06-16.

Data collected will include number of contributors, number of PRs, time taken to close/merge these PRs, and issues closed.

For more information, please visit [our informational page](https://sustainable-open-science-and-software.github.io/) or download our [participant information sheet](https://sustainable-open-science-and-software.github.io/assets/PIS_sustainable_software.pdf).
