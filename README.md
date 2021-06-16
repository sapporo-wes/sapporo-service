# sapporo-service

[![pytest](https://github.com/ddbj/sapporo-service/workflows/pytest/badge.svg)](https://github.com/ddbj/sapporo-service/actions?query=workflow%3Apytest)
[![flake8](https://github.com/ddbj/sapporo-service/workflows/flake8/badge.svg)](https://github.com/ddbj/sapporo-service/actions?query=workflow%3Aflake8)
[![isort](https://github.com/ddbj/sapporo-service/workflows/isort/badge.svg)](https://github.com/ddbj/sapporo-service/actions?query=workflow%3Aisort)
[![mypy](https://github.com/ddbj/sapporo-service/workflows/mypy/badge.svg)](https://github.com/ddbj/sapporo-service/actions?query=workflow%3Amypy)
[![Apache License](https://img.shields.io/badge/license-Apache%202.0-orange.svg?style=flat&color=important)](http://www.apache.org/licenses/LICENSE-2.0)

<img src="https://raw.githubusercontent.com/ddbj/sapporo/master/logo/sapporo-service.svg" width="400" style="display: block; margin-left: auto; margin-right: auto; margin-top: 30px; margin-bottom: 30px;" alt="sapporo-service logo">

[Japanese Document](https://github.com/ddbj/sapporo-service/blob/master/README_ja.md)

sapporo-service is a standard implementation conforming to the [Global Alliance for Genomics and Health](https://www.ga4gh.org) (GA4GH) [Workflow Execution Service](https://github.com/ga4gh/workflow-execution-service-schemas) (WES) API specification.

One of sapporo-service's features is the abstraction of workflow engines, which makes it easy to convert various workflow engines into WES.
Currently, the following workflow engines have been confirmed to work.

- [cwltool](https://github.com/common-workflow-language/cwltool)
- [nextflow](https://www.nextflow.io)
- [Toil (experimental)](https://toil.ucsc-cgl.org)
- [cromwell](https://github.com/broadinstitute/cromwell)
- [snakemake](https://snakemake.readthedocs.io/en/stable/)
- [ep3 (experimental)](https://github.com/tom-tan/ep3)

Another feature of sapporo-service is the mode that can only execute workflows registered by the system administrator.
This feature is useful when building a WES in a shared HPC environment.

## Install and Run

sapporo-service supports Python 3.6 or newer.

```bash
$ pip3 install sapporo
$ sapporo
```

### Docker

You can also launch sapporo with Docker.
In order to use Docker-in-Docker (DinD), you have to mount `docker.sock`, `/tmp`, etc.

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

There are two startup modes in sapporo-service.

- Standard WES mode (Default)
- Execute only registered workflows mode

These are switched with the startup argument `-run-only-registered-workflows`.
It can also be switched by giving `True` or `False` to the environment variable `SAPPORO_ONLY_REGISTERED_WORKFLOWS`.
**Startup arguments take priority over environment variables.**

#### Standard WES mode

As API specifications, please check [GitHub - GA4GH WES](https://github.com/ga4gh/workflow-execution-service-schemas).

**When using sapporo-service, It is different from the standard WES API specification, you must specify `workflow_engine_name` in the request parameter of `POST /runs`.**
I personally think this part is standard WES API specification's mistake, so I am sending a request to fix it.

#### Execute only registered workflows mode

As API specifications for the execute only registered workflows mode, please check [SwaggerUI - sapporo WES](https://suecharo.github.io/sapporo-swagger-ui/dist/).

Basically, it conforms to the standard WES API.
The changes are as follows.

- Executable workflows are returned by `GET /service-info` as `executable_workflows`.
- Specify `workflow_name` instead of `workflow_url` in `POST /runs`.

The following is an example of requesting `GET /service-info` in the execute only registered workflows mode.

```json
GET /service-info
{
  "auth_instructions_url": "https://github.com/ddbj/sapporo-service",
  "contact_info_url": "https://github.com/ddbj/sapporo-service",
  "default_workflow_engine_parameters": [],
  "executable_workflows": [
    {
      "workflow_attachment": [],
      "workflow_name": "CWL_trimming_and_qc_remote",
      "workflow_type": "CWL",
      "workflow_type_version": "v1.0",
      "workflow_url": "https://raw.githubusercontent.com/ddbj/sapporo-service/master/tests/resources/trimming_and_qc_remote.cwl"
    },
    {
      "workflow_attachment": [
        {
          "file_name": "fastqc.cwl",
          "file_url": "https://raw.githubusercontent.com/ddbj/sapporo-service/master/tests/resources/fastqc.cwl"
        },
        {
          "file_name": "trimming_pe.cwl",
          "file_url": "https://raw.githubusercontent.com/ddbj/sapporo-service/master/tests/resources/trimming_pe.cwl"
        }
      ],
      "workflow_name": "CWL_trimming_and_qc_local",
      "workflow_type": "CWL",
      "workflow_type_version": "v1.0",
      "workflow_url": "https://raw.githubusercontent.com/ddbj/sapporo-service/master/tests/resources/trimming_and_qc.cwl"
    }
  ],
  "supported_filesystem_protocols": ["http", "https", "file", "s3"],
  "supported_wes_versions": ["sapporo-wes-1.0.0"],
  "system_state_counts": {},
  "tags": {
    "debug": true,
    "get_runs": true,
    "registered_only_mode": true,
    "wes_name": "sapporo",
    "workflow_attachment": true
  },
  "workflow_engine_versions": {
    "cromwell": "55",
    "cwltool": "1.0.20191225192155",
    "ep3": "v1.0.0",
    "nextflow": "21.01.1-edge",
    "snakemake": "v5.32.0",
    "toil": "4.1.0"
  },
  "workflow_type_versions": {
    "CWL": { "workflow_type_version": ["v1.0", "v1.1", "v1.1.0-dev1"] },
    "Nextflow": { "workflow_type_version": ["v1.0"] },
    "Snakemake": { "workflow_type_version": ["v1.0"] },
    "WDL": { "workflow_type_version": ["1.0"] }
  }
}
```

The executable workflows are managed at [`executable_workflows.json`](https://github.com/ddbj/sapporo-service/blob/master/sapporo/executable_workflows.json). Also, the schema for this definition is [`executable_workflows.schema.json`](https://github.com/ddbj/sapporo-service/blob/master/sapporo/executable_workflows.schema.json). The default location of these files is under the application directory of sapporo-service. You can override them by using the startup argument `--executable-workflows` or the environment variable `SAPPORO_EXECUTABLE_WORKFLOWS`.

### Run Dir

sapporo-service manages the submitted workflows, workflow parameters, output files, etc.
on the file system. You can override the location of run dir by using the startup argument `--run-dir` or the environment variable `SAPPORO_RUN_DIR`.

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
Examples using `curl` are provided in [GitHub - sapporo/tests/curl](https://github.com/ddbj/sapporo-service/tree/master/tests/curl_example/post_runs).
Please use these as references.

### `run.sh`

We use [`run.sh`](https://github.com/ddbj/sapporo-service/blob/master/sapporo/run.sh) to abstract the workflow engine.
When `POST /runs` is called, sapporo-service fork the execution of `run.sh` after dumping the necessary files to run dir. Therefore, you can apply various workflow engines to WES by editing `run.sh`.

The default position of `run.sh` is under the application directory of sapporo-service. You can override it by using the startup argument `--run-sh` or the environment variable `SAPPORO_RUN_SH`.

### Other Startup Arguments

You can change the host and port used by the application by using the startup arguments (`--host` and `--port`) or the environment variables `SAPPORO_HOST` and `SAPPORO_PORT`.

The following three startup arguments and environment variables are provided to limit the WES.

- `--disable-get-runs`
  - `SAPPORO_GET_RUNS`: `True` or `False`.
  - Disable `GET /runs`.
    - When using WES with an unspecified number of people, by knowing the run_id, you can see the run's contents and cancel the run of other people.
    - Because run_id itself is automatically generated using `uuid4`, it is difficult to know it in brute force.
- `--disable-workflow-attachment`
  - `SAPPORO_WORKFLOW_ATTACHMENT`: `True` or `False`.
  - Disable `workflow_attachment` in `POST /runs`.
    - The `workflow_attachment` field is used to attach files for executing workflows.
    - There is a security concern because anything can be attached.
- `--url-prefix`.
  - `SAPPORO_URL_PREFIX`.
  - Set the URL PREFIX.
    - If `--url-prefix /foo/bar` is set, `GET /service-info` becomes `GET /foo/bar/service-info`.

The contents of the response of `GET /service-info` are managed in [`service-info.json`](https://github.com/ddbj/sapporo-service/blob/master/sapporo/service-info.json). The default location of `service-info.json` is under the application directory of sapporo-service. You can override by using the startup argument `--service-info` or the environment variable `SAPPORO_SERVICE_INFO`.

## Generate download link

sapporo-service provides the file and directory under run_dir as download link.

For details, please check `/runs/{ run_id}/data/path-to-file-or-dir` in [SwaggerUI - sapporo WES](https://suecharo.github.io/sapporo-swagger-ui/dist/) for more information.

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

## License

[Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0). See the [LICENSE](https://github.com/ddbj/sapporo-service/blob/master/LICENSE).

## Notice

Please note that this repository is participating in a study into sustainability
 of open source projects. Data will be gathered about this repository for
 approximately the next 12 months, starting from 2021-06-16.

Data collected will include number of contributors, number of PRs, time taken to
 close/merge these PRs, and issues closed.

For more information, please visit
[our informational page](https://sustainable-open-science-and-software.github.io/) or download our [participant information sheet](https://sustainable-open-science-and-software.github.io/assets/PIS_sustainable_software.pdf).
