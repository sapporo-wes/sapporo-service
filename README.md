# sapporo-service

[![DOI](https://zenodo.org/badge/220937589.svg)](https://zenodo.org/badge/latestdoi/220937589)
[![Apache License](https://img.shields.io/badge/license-Apache%202.0-orange.svg?style=flat&color=important)](http://www.apache.org/licenses/LICENSE-2.0)

<img src="https://raw.githubusercontent.com/sapporo-wes/sapporo/main/logo/sapporo-service.svg" width="400" style="display: block; margin-left: auto; margin-right: auto; margin-top: 30px; margin-bottom: 30px;" alt="sapporo-service logo">

The sapporo-service is a standard implementation conforming to the [Global Alliance for Genomics and Health](https://www.ga4gh.org) (GA4GH) [Workflow Execution Service](https://github.com/ga4gh/workflow-execution-service-schemas) (WES) API specification.

We have also extended the API specification. For more details, please refer to [`./sapporo-wes-spec-2.0.0.yml`](./sapporo-wes-spec-2.0.0.yml) for more details.

The service is compatible with the following workflow engines:

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

As of sapporo-service 2.0.0, an SQLite database (`sapporo.db`) has been added inside the run directory. This database is used to speed up `GET /runs` calls. The master data remains within each run directory, and the database is updated every 30 minutes while sapporo is running. If you need the latest run status, use `GET /runs/{run_id}` instead of `GET /runs`.

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

The sapporo-service provides a feature to clean up run directories that have a start time older than a specified number of days.
This can be configured using the `--run-remove-older-than-days` startup argument or the `SAPPORO_RUN_REMOVE_OLDER_THAN_DAYS` environment variable.

By setting this option, the sapporo-service will automatically remove run directories that are older than the specified number of days, helping to manage disk space and maintain a clean working environment.

### Generate RO-Crate

### Authentication

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

## Adding New Workflow Engines to Sapporo Service

The sapporo-service calls each workflow engine through the [`run.sh`](./sapporo/run.sh) script. Therefore, by editing `run.sh`, you can easily add new workflow engines or modify the behavior of existing ones. For an example of adding a new workflow engine, refer to the pull request that includes the addition of the `Streamflow` workflow engine: <https://github.com/sapporo-wes/sapporo-service/pull/29>

## License

This project is licensed under the [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) license. See the [LICENSE](./LICENSE) file for details.
