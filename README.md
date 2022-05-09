# sapporo-service

[![pytest](https://github.com/sapporo-wes/sapporo-service/workflows/pytest/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions?query=workflow%3Apytest)
[![flake8](https://github.com/sapporo-wes/sapporo-service/workflows/flake8/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions?query=workflow%3Aflake8)
[![isort](https://github.com/sapporo-wes/sapporo-service/workflows/isort/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions?query=workflow%3Aisort)
[![mypy](https://github.com/sapporo-wes/sapporo-service/workflows/mypy/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions?query=workflow%3Amypy)
[![DOI](https://zenodo.org/badge/220937589.svg)](https://zenodo.org/badge/latestdoi/220937589)
[![Apache License](https://img.shields.io/badge/license-Apache%202.0-orange.svg?style=flat&color=important)](http://www.apache.org/licenses/LICENSE-2.0)

<img src="https://raw.githubusercontent.com/sapporo-wes/sapporo/main/logo/sapporo-service.svg" width="400" style="display: block; margin-left: auto; margin-right: auto; margin-top: 30px; margin-bottom: 30px;" alt="sapporo-service logo">

[Japanese Document](https://github.com/sapporo-wes/sapporo-service/blob/main/README_ja.md)

The sapporo-service is a standard implementation conforming to the [Global Alliance for Genomics and Health](https://www.ga4gh.org) (GA4GH) [Workflow Execution Service](https://github.com/ga4gh/workflow-execution-service-schemas) (WES) API specification.

Also, we have extended the API specification.
Please check [SwaggerHub - sapporo-wes](https://app.swaggerhub.com/apis/suecharo/sapporo-wes/sapporo-wes-1.0.1-oas3).

One of sapporo-service's features is the abstraction of workflow engines, making it easy to convert various workflow engines into WES.
Currently, the following workflow engines have been confirmed to work.

- [cwltool](https://github.com/common-workflow-language/cwltool)
- [nextflow](https://www.nextflow.io)
- [Toil (experimental)](https://toil.ucsc-cgl.org)
- [cromwell](https://github.com/broadinstitute/cromwell)
- [snakemake](https://snakemake.readthedocs.io/en/stable/)
- [ep3 (experimental)](https://github.com/tom-tan/ep3)
- [StreamFlow (experimental)](https://github.com/alpha-unito/streamflow)

Another feature of the sapporo-service is the mode that can only execute workflows registered by the system administrator.
This feature is useful when building a WES in a shared HPC environment.

## Install and Run

The sapporo-service supports Python 3.6 or newer.

```bash
$ pip3 install sapporo
$ sapporo
```

### Docker

You can also launch the sapporo-service with Docker.
To use Docker-in-Docker (DinD), you must mount `docker.sock`, `/tmp`, etc.

```bash
# Launch
$ docker-compose up -d

# Launch confirmation
$ docker-compose logs
```

## Usage

The help for the sapporo-service startup command is as follows.

```bash
$ sapporo --help
usage: sapporo [-h] [--host] [-p] [--debug] [-r] [--disable-get-runs]
               [--disable-workflow-attachment]
               [--run-only-registered-workflows] [--service-info]
               [--executable-workflows] [--run-sh] [--url-prefix]

Implementation of a GA4GH workflow execution service that can easily support
various workflow runners.

optional arguments:
  -h, --help            show this help message and exit
  --host                Host address of Flask. (default: 127.0.0.1)
  -p , --port           Port of Flask. (default: 1122)
  --debug               Enable debug mode of Flask.
  -r , --run-dir        Specify the run dir. (default: ./run)
  --disable-get-runs    Disable endpoint of `GET /runs`.
  --disable-workflow-attachment
                        Disable `workflow_attachment` on endpoint `Post
                        /runs`.
  --run-only-registered-workflows
                        Run only registered workflows. Check the registered
                        workflows using `GET /service-info`, and specify
                        `workflow_name` in the `POST /run`.
  --service-info        Specify `service-info.json`. The
                        supported_wes_versions, system_state_counts and
                        workflows are overwritten in the application.
  --executable-workflows
                        Specify `executable-workflows.json`.
  --run-sh              Specify `run.sh`.
  --url-prefix          Specify the prefix of the url (e.g. --url-prefix /foo
                        -> /foo/service-info).
```

### Operating Mode

There are two startup modes in the sapporo-service.

- Standard WES mode (Default)
- Execute only registered workflows mode

These are switched with the startup argument `--run-only-registered-workflows`.
It can also be switched by giving `True` or `False` to the environment variable `SAPPORO_ONLY_REGISTERED_WORKFLOWS`.
**Startup arguments take priority over environment variables.**

#### Standard WES mode

As the API specifications, please check [SwaggerHub - sapporo-wes - RunWorkflow](https://app.swaggerhub.com/apis/suecharo/sapporo-wes/sapporo-wes-1.0.1-oas3#/default/RunWorkflow).

**When using the sapporo-service, It is different from the standard WES API specification; you must specify `workflow_engine_name` in the request parameter of `POST /runs`.**
We think this part is a standard WES API specification mistake, so we request fixing it.

#### Execute only registered workflows mode

As the API specifications for executing only registered workflows mode, please check [SwaggerHub - sapporo-wes](https://app.swaggerhub.com/apis/suecharo/sapporo-wes/sapporo-wes-1.0.0).

It conforms to the standard WES API.
The changes are as follows.

- Executable workflows are returned by `GET /executable_workflows`.
- Specify `workflow_name` instead of `workflow_url` in `POST /runs`.

The executable workflows are managed at [`executable_workflows.json`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/executable_workflows.json).
Also, the schema for this definition is [`executable_workflows.schema.json`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/executable_workflows.schema.json). The default location of these files is under the application directory of the sapporo-service. You can override them using the startup argument `--executable-workflows` or the environment variable `SAPPORO_EXECUTABLE_WORKFLOWS`.

For more information, see [SwaggerUI - sapporo-wes - GetExecutableWorkflows](https://app.swaggerhub.com/apis/suecharo/sapporo-wes/sapporo-wes-1.0.1-oas3#/default/GetExecutableWorkflows).

### Run Dir

The sapporo-service manages the submitted workflows, workflow parameters, output files, etc., on the file system.
You can override the location of run dir by using the startup argument `--run-dir` or the environment variable `SAPPORO_RUN_DIR`.

The run dir structure is as follows. You can initialize and delete each run by physical deletion with `rm`.

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
        │   ├── ERR034597_1.small.fq.trimmed.1P.fq
        │   ├── ERR034597_1.small.fq.trimmed.1U.fq
        │   ├── ERR034597_1.small.fq.trimmed.2P.fq
        │   ├── ERR034597_1.small.fq.trimmed.2U.fq
        │   ├── ERR034597_1.small_fastqc.html
        │   └── ERR034597_2.small_fastqc.html
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

The execution of `POST /runs` is very complex.
Examples using `curl` are provided in [GitHub - sapporo/tests/curl](https://github.com/sapporo-wes/sapporo-service/tree/main/tests/curl_example/post_runs).
Please use these as references.

### `run.sh`

We use [`run.sh`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/run.sh) to abstract the workflow engine.
When `POST /runs` is called, the sapporo-service fork the execution of `run.sh` after dumping the necessary files to run dir. Therefore, you can apply various workflow engines to WES by editing `run.sh`.

The default position of `run.sh` is under the application directory of the sapporo-service. You can override it using the startup argument `--run-sh` or the environment variable `SAPPORO_RUN_SH`.

### Other Startup Arguments

You can change the host and port used by the application by using the startup arguments (`--host` and `--port`) or the environment variables `SAPPORO_HOST` and `SAPPORO_PORT`.

The following three startup arguments and environment variables limit the WES.

- `--disable-get-runs`
  - `SAPPORO_GET_RUNS`: `True` or `False`.
  - Disable `GET /runs`.
    - When using WES with an unspecified number of people, by knowing the run_id, you can see the run's contents and cancel the run of other people.
      It is difficult to know it in brute force because run_id itself is automatically generated using `uuid4`.
- `--disable-workflow-attachment`
  - `SAPPORO_WORKFLOW_ATTACHMENT`: `True` or `False`.
  - Disable `workflow_attachment` in `POST /runs`.
    - The `workflow_attachment` field is used to attach files for executing workflows.
    - There is a security concern because anything can be attached.
- `--url-prefix`.
  - `SAPPORO_URL_PREFIX`.
  - Set the URL PREFIX.
    - If `--url-prefix /foo/bar` is set, `GET /service-info` becomes `GET /foo/bar/service-info`.

The contents of the response of `GET /service-info` are managed in [`service-info.json`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/service-info.json). The default location of `service-info.json` is under the application directory of the sapporo-service. You can override by using the startup argument `--service-info` or the environment variable `SAPPORO_SERVICE_INFO`.

## Generate download link

The sapporo-service provides the file and directory under run_dir as a download link.

For more information, see [SwaggerUI - sapporo-wes - GetData](https://app.swaggerhub.com/apis/suecharo/sapporo-wes/sapporo-wes-1.0.1-oas3#/default/GetData).

## Parse workflow

The sapporo-service provides the feature to check the workflow document's type, version, and inputs.

For more information, see [SwaggerUI - sapporo-wes - GetData](https://app.swaggerhub.com/apis/suecharo/sapporo-wes/sapporo-wes-1.0.1-oas3#/default/GetData).

## Development

You can start the development environment as follows.

```bash
$ docker-compose -f docker-compose.dev.yml up -d --build
$ docker-compose -f docker-compose.dev.yml exec app bash
```

We use [flake8](https://pypi.org/project/flake8/), [isort](https://github.com/timothycrosley/isort), and [mypy](http://mypy-lang.org) as a linter.

```bash
$ bash ./tests/lint_and_style_check/flake8.sh
$ bash ./tests/lint_and_style_check/isort.sh
$ bash ./tests/lint_and_style_check/mypy.sh

$ bash ./tests/lint_and_style_check/run_all.sh
```

We use [pytest](https://docs.pytest.org/en/latest/) as a tester.

```bash
$ pytest .
```

## Add new Workflow Engines to Sapporo Service

Have a look at the [`run.sh`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/run.sh) script called from Python.
This shell script will receive a request with Workflow Engine such as `cwltool` and will invoke the `run_cwltool` bash function.

That function will execute a Bash Shell command to start a Docker container for the Workflow Engine, and monitor its exit status.
For a complete example, please refer to this pull request: <https://github.com/sapporo-wes/sapporo-service/pull/29>

## License

[Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0). See the [LICENSE](https://github.com/sapporo-wes/sapporo-service/blob/main/LICENSE).

## Notice

Please note that this repository is participating in a study into sustainability of open source projects. Data will be gathered about this repository for approximately the next 12 months, starting from 2021-06-16.

Data collected will include number of contributors, number of PRs, time taken to close/merge these PRs, and issues closed.

For more information, please visit [our informational page](https://sustainable-open-science-and-software.github.io/) or download our [participant information sheet](https://sustainable-open-science-and-software.github.io/assets/PIS_sustainable_software.pdf).
