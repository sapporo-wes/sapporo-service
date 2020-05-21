# SAPPORO-service

[![pytest](https://github.com/ddbj/SAPPORO-service/workflows/pytest/badge.svg)](https://github.com/ddbj/SAPPORO-service/actions?query=workflow%3Apytest)
[![flake8](https://github.com/ddbj/SAPPORO-service/workflows/flake8/badge.svg)](https://github.com/ddbj/SAPPORO-service/actions?query=workflow%3Aflake8)
[![isort](https://github.com/ddbj/SAPPORO-service/workflows/isort/badge.svg)](https://github.com/ddbj/SAPPORO-service/actions?query=workflow%3Aisort)
[![mypy](https://github.com/ddbj/SAPPORO-service/workflows/mypy/badge.svg)](https://github.com/ddbj/SAPPORO-service/actions?query=workflow%3Amypy)
[![Apache License](https://img.shields.io/badge/license-Apache%202.0-orange.svg?style=flat&color=important)](http://www.apache.org/licenses/LICENSE-2.0)

<img src="https://raw.githubusercontent.com/ddbj/SAPPORO/master/logo/SAPPORO-Service.svg" width="400" style="display: block; margin-left: auto; margin-right: auto;" alt="SAPPORO-service logo">

[Japanese Document](https://github.com/ddbj/SAPPORO-service/blob/master/README_ja.md)

SAPPORO is a standard implementation conforming to the [Global Alliance for Genomics and Health](https://www.ga4gh.org) (GA4GH) [Workflow Execution Service](https://github.com/ga4gh/workflow-execution-service-schemas) (WES) API specification.

One of SAPPORO's features is the abstraction of workflow engines, which makes it easy to convert various workflow engines into WES. The following workflow engines have been confirmed to be working at present.

- [cwltool](https://github.com/common-workflow-language/cwltool)
- [nextflow](https://www.nextflow.io)
- [Toil](https://toil.ucsc-cgl.org)
- [cromwell](https://github.com/broadinstitute/cromwell)
- [snakemake](https://snakemake.readthedocs.io/en/stable/)

Another feature of SAPPORO is the mode that can only execute workflows registered by the system administrator. This feature is useful when building a WES in a shared HPC environment.

## Install and Run

SAPPORO supports Python 3.6 or newer.

```bash
$ pip3 install sapporo
$ sapporo
```

### Docker

You can also launch it with Docker.
To use Docker-in-Docker (DinD), you have to mount `docker.sock`, `/tmp`, etc.

```bash
# Launch
$ docker-compose up -d

# Launch confirmation
$ docker-compose logs
```

## Usage

The help for the SAPPORO startup command is as follows.

```bash
$ sapporo --help
usage: sapporo [-h] [--host] [-p] [--debug] [-r] [--disable-get-runs]
               [--disable-workflow-attachment]
               [--run-only-registered-workflows] [--service-info]
               [--executable-workflows] [--run-sh]

Implementation of a GA4GH workflow execution service that can easily
support various workflow runners.

optional arguments:
  -h, --help            show this help message and exit
  --host                Host address of Flask. (default: 127.0.0.1)
  -p , --port           Port of Flask. (default: 8080)
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
```

### Operating Mode

There are two startup modes in SAPPORO.

- Standard WES mode (Default)
- Execute only registered workflows mode

These are switched with the startup argument `-run-only-registered-workflows`. It can also be switched by giving `True` or `False` to the environment variable `SAPPORO_ONLY_REGISTERED_WORKFLOWS`. Startup arguments take priority over environment variables.

#### Standard WES mode

As API specifications, please check [GitHub - GA4GH WES](https://github.com/ga4gh/workflow-execution-service-schemas) and [SwaggerUI - GA4GH WES](https://suecharo.github.io/genpei-swagger-ui/dist/).

**When using SAPPORO, It is different from the standard WES API specification, you must specify `workflow_engine_name` in the request parameter of `POST /runs`.** I personally think this part is standard WES API specification's mistake, so I am sending a request to fix it.

#### Execute only registered workflows mode

As API specifications for the execute only registered workflows mode, please check [SwaggerUI - SAPPORO WES](https://suecharo.github.io/sapporo-swagger-ui/dist/).

Basically, it conforms to the standard WES API. The changes are as follows.

- Executable workflows are returned by `GET /service-info` as `executable_workflows`.
- Specify `workflow_name` instead of `workflow_url` in `POST /runs`.

The following is an example of requesting `GET /service-info` in the execute only registered workflows mode.

```json
GET /service-info
{
  "auth_instructions_url": "https://github.com/ddbj/SAPPORO-service",
  "contact_info_url": "https://github.com/ddbj/SAPPORO-service",
  "default_workflow_engine_parameters": [],
  "executable_workflows": [
    {
      "workflow_attachment": [],
      "workflow_name": "CWL_trimming_and_qc_remote",
      "workflow_type": "CWL",
      "workflow_type_version": "v1.0",
      "workflow_url": "https://raw.githubusercontent.com/ddbj/SAPPORO-service/master/tests/resources/trimming_and_qc_remote.cwl"
    },
    {
      "workflow_attachment": [
        {
          "file_name": "fastqc.cwl",
          "file_url": "https://raw.githubusercontent.com/ddbj/SAPPORO-service/master/tests/resources/fastqc.cwl"
        },
        {
          "file_name": "trimming_pe.cwl",
          "file_url": "https://raw.githubusercontent.com/ddbj/SAPPORO-service/master/tests/resources/trimming_pe.cwl"
        }
      ],
      "workflow_name": "CWL_trimming_and_qc_local",
      "workflow_type": "CWL",
      "workflow_type_version": "v1.0",
      "workflow_url": "https://raw.githubusercontent.com/ddbj/SAPPORO-service/master/tests/resources/trimming_and_qc.cwl"
    }
  ],
  "supported_filesystem_protocols": [
    "http",
    "https",
    "file"
  ],
  "supported_wes_versions": [
    "sapporo-wes-1.1"
  ],
  "system_state_counts": {},
  "tags": {
    "debug": true,
    "get_runs": true,
    "registered_only_mode": true,
    "run_dir": "/home/ubuntu/git/github.com/ddbj/SAPPORO-service/run",
    "wes_name": "sapporo",
    "workflow_attachment": true
  },
  "workflow_engine_versions": {
    "cromwell": "50",
    "cwltool": "1.0.20191225192155",
    "nextflow": "20.04.1",
    "snakemake": "v5.17.0",
    "toil": "4.1.0"
  },
  "workflow_type_versions": {
    "CWL": {
      "workflow_type_version": [
        "v1.0",
        "v1.1",
        "v1.1.0-dev1"
      ]
    }
  }
}
```

The executable workflows are managed at [`executable_workflows.json`](https://github.com/ddbj/SAPPORO-service/blob/master/sapporo/executable_workflows.json). Also, the schema for this definition is [`executable_workflows.schema.json`](https://github.com/ddbj/SAPPORO-service/blob/master/sapporo/executable_workflows.schema.json). The default location of these files is under the application directory of SAPPORO. You can override them by using the startup argument `--executable-workflows` or the environment variable `SAPPORO_EXECUTABLE_WORKFLOWS`.

### Run Dir

SAPPORO manages the submitted workflows, workflow parameters, output files, etc. on the file system. You can override the location of run dir by using the startup argument `--run-dir` or the environment variable `SAPPORO_RUN_DIR`.

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

The execution of `POST /runs` is very complex. Examples using Python's [requests](https://requests.readthedocs.io/en/master/) are provided in [GitHub - sapporo/tests/post_runs_examples](https://github.com/ddbj/SAPPORO-service/tree/master/tests/post_runs_examples). Please use this as a reference.

### `run.sh`

We use [`run.sh`](https://github.com/ddbj/SAPPORO-service/blob/master/sapporo/run.sh) to abstract the workflow engine. When `POST /runs` is called, SAPPORO fork the execution of `run.sh` after dumping the necessary files to run dir. Therefore, you can apply various workflow engines to WES by editing `run.sh`.

The default position of `run.sh` is under the application directory of SAPPORO. You can override it by using the startup argument `--run-sh` or the environment variable `SAPPORO_RUN_SH`.

### Other Startup Arguments

You can change the host and port used by the application by using the startup arguments (`--host` and `--port`) or the environment variables `SAPPORO_HOST` and `SAPPORO_PORT`.

The following two startup arguments and environment variables are provided to limit the WES.

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

The contents of the response of `GET /service-info` are managed in [`service-info.json`](https://github.com/ddbj/SAPPORO-service/blob/master/sapporo/service-info.json). The default location of `service-info.json` is under the application directory of SAPPORO. You can override by using the startup argument `--service-info` or the environment variable `SAPPORO_SERVICE_INFO`.

## Development

You can start the development environment as follows.

```bash
$ docker-compose -f docker-compose.dev.yml up -d --build
$ docker-compose -f docker-compose.dev.yml exec app bash
```

We use [flake8](https://pypi.org/project/flake8/), [isort](https://github.com/timothycrosley/isort), and [mypy](http://mypy-lang.org) as the Linter.

```bash
$ bash ./tests/lint_and_style_check/flake8.sh
$ bash ./tests/lint_and_style_check/isort.sh
$ bash ./tests/lint_and_style_check/mypy.sh
```

We use [pytest](https://docs.pytest.org/en/latest/) as a Test Tool.

```bash
$ pytest .
```

## License

[Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0). See the [LICENSE](https://github.com/ddbj/SAPPORO-service/blob/master/LICENSE).
