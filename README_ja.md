# SAPPORO-service

[![pytest](https://github.com/ddbj/SAPPORO-service/workflows/pytest/badge.svg)](https://github.com/ddbj/SAPPORO-service/actions?query=workflow%3Apytest)
[![flake8](https://github.com/ddbj/SAPPORO-service/workflows/flake8/badge.svg)](https://github.com/ddbj/SAPPORO-service/actions?query=workflow%3Aflake8)
[![isort](https://github.com/ddbj/SAPPORO-service/workflows/isort/badge.svg)](https://github.com/ddbj/SAPPORO-service/actions?query=workflow%3Aisort)
[![mypy](https://github.com/ddbj/SAPPORO-service/workflows/mypy/badge.svg)](https://github.com/ddbj/SAPPORO-service/actions?query=workflow%3Amypy)
[![Apache License](https://img.shields.io/badge/license-Apache%202.0-orange.svg?style=flat&color=important)](http://www.apache.org/licenses/LICENSE-2.0)

<img src="https://raw.githubusercontent.com/ddbj/SAPPORO/master/logo/SAPPORO-Service.svg" width="400" style="display: block; margin-left: auto; margin-right: auto;" alt="SAPPORO-service logo">

SAPPORO は、[Global Alliance for Genomics and Health](https://www.ga4gh.org) (GA4GH) により制定された [Workflow Execution Service](https://github.com/ga4gh/workflow-execution-service-schemas) (WES) API 定義に準拠した標準実装です。

SAPPORO の特徴として、workflow engine の抽象化を試みており、様々な workflow engine を容易に WES 化できます。
現在、稼働が確認されている workflow engine は、下記のとおりです。

- [cwltool](https://github.com/common-workflow-language/cwltool)
- [Nextflow](https://www.nextflow.io)
- [Toil](https://toil.ucsc-cgl.org)
- [cromwell](https://github.com/broadinstitute/cromwell)
- [snakemake](https://snakemake.readthedocs.io/en/stable/)
- [ep3](https://github.com/tom-tan/ep3)

もう一つの特徴として、管理者により登録された workflow のみ実行できるモードへと切り替えられます。
この機能は、共有の HPC 環境で WES を構築する時に有用です。

## Install and Run

Python 3.6 以上を想定しています。

```bash
$ pip3 install sapporo
$ sapporo
```

### Docker

Docker を用いた利用も想定しています。
Docker-in-Docker (DinD) を使用するため、`docker.sock` や `/tmp` などを mount しなければなりません。

```bash
# 起動
$ docker-compose up -d

# 起動確認
$ docker-compose logs
```

## Usage

SAPPORO の起動コマンドのヘルプは以下の通りです。

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
  --url-prefix          Specify the prefix of the url (e.g. --url-prefix /foo
                        -> /foo/service-info).
```

### Operating Mode

SAPPORO には 2 つのモードがあります。

- 標準 WES モード (Default)
- 登録された workflow のみを実行するモード

これらの切り替えは、起動時引数 の `--run-only-registered-workflows` で切り替えられます。
また、環境変数の `SAPPORO_ONLY_REGISTERED_WORKFLOWS` に `True` or `False` を与えることでも切り替えられます。
全ての option について共通ですが、**起動時引数は環境変数より優先されます**。

#### 標準 WES モード

標準 WES モードの API 仕様は、[GitHub - GA4GH WES](https://github.com/ga4gh/workflow-execution-service-schemas) や [SwaggerUI - GA4GH WES](https://suecharo.github.io/genpei-swagger-ui/dist/) を確認してください。

**標準 WES API の仕様と異なる点として、`POST /runs` の request parameter に `workflow_engine_name` を指定する必要があります。**
これは、個人的には、標準 WES API 仕様の不備であると考えていて、修正要求を出しています。

#### 登録された workflow のみを実行するモード

登録された workflow のみを実行するモードの API 仕様は、[SwaggerUI - SAPPORO WES](https://suecharo.github.io/sapporo-swagger-ui/dist/) を確認してください。

基本的には、標準 WES API を準拠しています。具体的な変更点としては、以下の通りです。

- `GET /service-info` にて、`executable_workflows` として実行可能な workflow が返される。
- `POST /runs` にて、`workflow_url` の代わりに `workflow_name` を指定する。

以下は、登録された workflow のみを実行するモードにおいて、`GET /service-info` を実行した例です。

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
    "file",
    "s3"
  ],
  "supported_wes_versions": [
    "sapporo-wes-1.0.0"
  ],
  "system_state_counts": {
    "COMPLETE": 6
  },
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
    "ep3": "v1.0.0",
    "nextflow": "21.01.1-edge",
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
    },
    "Nextflow": {
      "workflow_type_version": [
        "v1.0"
      ]
    }
  }
}
```

実行できる workflow は [`executable_workflows.json`](https://github.com/ddbj/SAPPORO-service/blob/master/sapporo/executable_workflows.json) にて管理されています。
また、この定義の schema は [`executable_workflows.schema.json`](https://github.com/ddbj/SAPPORO-service/blob/master/sapporo/executable_workflows.schema.json) です。
これらの file の default の位置は、SAPPORO のアプリケーション直下ですが、起動時引数の `--executable-workflows` や環境変数の `SAPPORO_EXECUTABLE_WORKFLOWS` で上書きできます。

### Run Dir

SAPPORO は、投入された workflow や workflow parameter、output files などを file system 上で管理しています。
これら全ての file をまとめた directory を run dir と呼んでおり、default は `${PWD}/run` です。run dir の場所は、起動時引数 `--run-dir` や環境変数 `SAPPORO_RUN_DIR` で上書きできます。

run dir 構造は、以下のようになっており、それぞれの run における file 群が配置されています。初期化やそれぞれの run の削除は `rm` を用いた物理的な削除により行えます。

```bash
$ tree run
.
└── 29
    └── 29109b85-7935-4e13-8773-9def402c7775
        ├── cmd.txt
        ├── end_time.txt
        ├── exe
        │   └── workflow_params.json
        ├── exit_code.txt
        ├── outputs
        │   ├── ERR034597_1.small.fq.trimmed.1P.fq
        │   ├── ERR034597_1.small.fq.trimmed.1U.fq
        │   ├── ERR034597_1.small.fq.trimmed.2P.fq
        │   ├── ERR034597_1.small.fq.trimmed.2U.fq
        │   ├── ERR034597_1.small_fastqc.html
        │   └── ERR034597_2.small_fastqc.html
        ├── outputs.json
        ├── run.pid
        ├── run_request.json
        ├── start_time.txt
        ├── state.txt
        ├── stderr.log
        ├── stdout.log
        └── workflow_engine_params.txt
├── 2d
│   └── ...
└── 6b
    └── ...
```

`POST /runs` の実行は非常に複雑です。
`curl` を用いた例として、[GitHub - sapporo/tests/curl](https://github.com/ddbj/SAPPORO-service/tree/master/tests/curl) が用意されています。
参考にしてください。

### `run.sh`

workflow engine の抽象化を shell script の [`run.sh`](https://github.com/ddbj/SAPPORO-service/blob/master/sapporo/run.sh) で行っています。
`POST /runs` が呼ばれると、SAPPORO は必要な file 群を run dir に dump した後、`run.sh` の実行を fork します。
そのため、`run.sh` を編集することによって、様々な workflow engine の WES 化を行えます。

`run.sh` の default の位置は、SAPPORO のアプリケーション直下ですが、起動時引数の `--run-sh` や環境変数の `SAPPORO_RUN_SH` で上書きできます。

### Other Startup Arguments

起動時引数 (`--host` and `--port`) を指定することで、起動 Host や Port を変更できます。また、これらの引数に対応する環境変数として、`SAPPORO_HOST`, `SAPPORO_PORT` が用意されています。

WES の機能を制限するための起動時引数・環境変数として、下の 3 つが用意されています。

- `--disable-get-runs`
  - `SAPPORO_GET_RUNS`: `True` or `False`
  - `GET /runs` を使用不可にする。
    - 不特定多数で利用している際、他の人の run_id を知ることで、run の内容や run の cancel を実行できるため。
    - run_id 自体は、`uuid4` で自動生成されるため、総当りで把握することは困難である。
- `--disable-workflow-attachment`
  - `SAPPORO_WORKFLOW_ATTACHMENT`: `True` or `False`
  - `POST /runs` における `workflow_attachment` を使用不可能にする。
    - `workflow_attachment` は workflow を実行する際に必要な file を添付するための field である。
    - 何でも添付できるため、セキュリティ的な懸念がある。
- `--url-prefix`
  - `SAPPORO_URL_PREFIX`
  - URL PREFIX を設定する。
    - `--url-prefix /foo/bar` とした場合、`GET /service-info` が `GET /foo/bar/service-info` となる

`GET /service-info` の response の中身として、[`service-info.json`](https://github.com/ddbj/SAPPORO-service/blob/master/sapporo/service-info.json) で管理しています。
`service-info.json` の default の位置は、SAPPORO のアプリケーション直下ですが、起動時引数の `--service-info` や環境変数の `SAPPORO_SERVICE_INFO` で上書きできます。

## Development

開発環境は以下で起動します。

```bash
$ docker-compose -f docker-compose.dev.yml up -d --build
$ docker-compose -f docker-compose.dev.yml exec app bash
```

Linter として、[flake8](https://pypi.org/project/flake8/), [isort](https://github.com/timothycrosley/isort), [mypy](http://mypy-lang.org) を用いています。

それぞれの実行方法は以下のとおりです。

```bash
$ bash ./tests/lint_and_style_check/flake8.sh
$ bash ./tests/lint_and_style_check/isort.sh
$ bash ./tests/lint_and_style_check/mypy.sh

$ bash ./tests/lint_and_style_check/run_all.sh
```

Tester として、[pytest](https://docs.pytest.org/en/latest/) を用いてます。

実行方法は以下のとおりです。

```bash
$ pytest .
```

## License

[Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).
See the [LICENSE](https://github.com/ddbj/SAPPORO-service/blob/master/LICENSE).
