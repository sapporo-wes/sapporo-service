# sapporo-service

[![pytest](https://github.com/sapporo-wes/sapporo-service/workflows/pytest/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions?query=workflow%3Apytest)
[![flake8](https://github.com/sapporo-wes/sapporo-service/workflows/flake8/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions?query=workflow%3Aflake8)
[![isort](https://github.com/sapporo-wes/sapporo-service/workflows/isort/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions?query=workflow%3Aisort)
[![mypy](https://github.com/sapporo-wes/sapporo-service/workflows/mypy/badge.svg)](https://github.com/sapporo-wes/sapporo-service/actions?query=workflow%3Amypy)
[![Apache License](https://img.shields.io/badge/license-Apache%202.0-orange.svg?style=flat&color=important)](http://www.apache.org/licenses/LICENSE-2.0)

<img src="https://raw.githubusercontent.com/sapporo-wes/sapporo/main/logo/sapporo-service.svg" width="400" style="display: block; margin-left: auto; margin-right: auto; margin-top: 30px; margin-bottom: 30px;" alt="sapporo-service logo">

sapporo-service は、[Global Alliance for Genomics and Health](https://www.ga4gh.org) (GA4GH) により制定された [Workflow Execution Service](https://github.com/ga4gh/workflow-execution-service-schemas) (WES) API 定義に準拠した標準実装です。

また、API 定義として、sapporo 独自の拡張を行っています。
API 仕様として、[SwaggerHub - sapporo-wes](https://app.swaggerhub.com/apis/suecharo/sapporo-wes/sapporo-wes-1.0.1-oas3) を確認してください。

sapporo-service の特徴として、workflow engine の抽象化を試みており、様々な workflow engine を容易に WES 化できます。
現在、稼働が確認されている workflow engine は、下記のとおりです。

- [cwltool](https://github.com/common-workflow-language/cwltool)
- [nextflow](https://www.nextflow.io)
- [Toil (experimental)](https://toil.ucsc-cgl.org)
- [cromwell](https://github.com/broadinstitute/cromwell)
- [snakemake](https://snakemake.readthedocs.io/en/stable/)
- [ep3 (experimental)](https://github.com/tom-tan/ep3)
- [StreamFlow (experimental)](https://github.com/alpha-unito/streamflow)

もう 1 つの特徴として、管理者により登録された workflow のみ実行できるモードへと切り替えられます。
この機能は、共有の HPC 環境で WES を構築する時に有用です。

## Install and Run

Python 3.7 以上を想定しています。

```bash
$ pip3 install sapporo
$ sapporo
```

### Docker

Docker を用いた利用も想定しています。
Docker-in-Docker (DinD) を使用するため、`docker.sock` や `/tmp` などを mount しなければなりません。

```bash
# 起動
$ docker compose up -d

# 起動確認
$ docker compose logs
```

## Usage

sapporo-service の起動コマンドのヘルプは以下の通りです。

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

sapporo-service には 2 つのモードがあります。

- 標準 WES モード (Default)
- 登録された workflow のみを実行するモード

これらの切り替えは、起動時引数 の `--run-only-registered-workflows` で切り替えられます。
また、環境変数の `SAPPORO_ONLY_REGISTERED_WORKFLOWS` に `True` or `False` を与えることでも切り替えられます。
全ての option について共通ですが、**起動時引数は環境変数より優先されます**。

#### 標準 WES モード

標準 WES モードの API 仕様は、[GitHub - GA4GH WES](https://github.com/ga4gh/workflow-execution-service-schemas) を確認してください。

**標準 WES API の仕様と異なる点として、`POST /runs` の request parameter に `workflow_engine_name` を指定する必要があります。**
これは、個人的には、標準 WES API 仕様の不備であると考えており、修正要求を出しています。

#### 登録された workflow のみを実行するモード

登録された workflow のみを実行するモードの API 仕様は、[SwaggerHub - sapporo-wes - RunWorkflow](https://app.swaggerhub.com/apis/suecharo/sapporo-wes/sapporo-wes-1.0.1-oas3#/default/RunWorkflow) を確認してください。

基本的には、標準 WES API を準拠しています。具体的な変更点としては、以下の通りです。

- `GET /executable_workflows` として実行可能な workflow が返される。
- `POST /runs` にて、`workflow_url` の代わりに `workflow_name` を指定する。

実行できる workflow は [`executable_workflows.json`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/executable_workflows.json) にて管理されています。
また、この定義の schema は [`executable_workflows.schema.json`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/executable_workflows.schema.json) です。
これらの file の default の位置は、sapporo-service のアプリケーション直下ですが、起動時引数の `--executable-workflows` や環境変数の `SAPPORO_EXECUTABLE_WORKFLOWS` で上書きできます。

詳しくは、[SwaggerUI - sapporo-wes - GetExecutableWorkflows](https://app.swaggerhub.com/apis/suecharo/sapporo-wes/sapporo-wes-1.0.1-oas3#/default/GetExecutableWorkflows) を確認してください。

### Run Dir

sapporo-service は、投入された workflow や workflow parameter、output files などを file system 上で管理しています。
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
`curl` を用いた例として、[GitHub - sapporo/tests/curl_example/post_runs](https://github.com/sapporo-wes/sapporo-service/tree/main/tests/curl_example/post_runs) が用意されています。
参考にしてください。

### `run.sh`

workflow engine の抽象化を shell script の [`run.sh`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/run.sh) で行っています。
`POST /runs` が呼ばれると、sapporo-service は必要な file 群を run dir に dump した後、`run.sh` の実行を fork します。
そのため、`run.sh` を編集することによって、様々な workflow engine の WES 化を行えます。

`run.sh` の default の位置は、sapporo-service のアプリケーション直下ですが、起動時引数の `--run-sh` や環境変数の `SAPPORO_RUN_SH` で上書きできます。

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

`GET /service-info` の response の中身として、[`service-info.json`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/service-info.json) で管理しています。
`service-info.json` の default の位置は、sapporo-service のアプリケーション直下ですが、起動時引数の `--service-info` や環境変数の `SAPPORO_SERVICE_INFO` で上書きできます。

### Generate download link

sapporo-service は run_dir 以下の file と directory を download link として提供します。

詳しくは、[SwaggerUI - sapporo-wes - ParseWorkflow](https://app.swaggerhub.com/apis/suecharo/sapporo-wes/sapporo-wes-1.0.1-oas3#/default/ParseWorkflow) を確認してください。

### Parse workflow

sapporo-service は、workflow document をパースして、workflow の type や version、inputs を調べる機能を提供します。

詳しくは、[SwaggerUI - sapporo-wes - GetData](https://app.swaggerhub.com/apis/suecharo/sapporo-wes/sapporo-wes-1.0.1-oas3#/default/GetData) を確認してください。

### Generate RO-Crate

The sapporo-service generates RO-Crate from the run_dir after the workflow execution is completed as `ro-crate-metadata.json` in the run_dir.

Please see, [ro-crate-metadata-example.json](./tests/ro-crate-metadata-example.json) as an example.

## Development

開発環境は以下で起動します。

```bash
$ docker compose -f docker-compose.dev.yml up -d --build
$ docker compose -f docker-compose.dev.yml exec app bash
```

Linter として、[flake8](https://pypi.org/project/flake8/), [isort](https://github.com/timothycrosley/isort), [mypy](http://mypy-lang.org) を用いてます。

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

## Add new Workflow Engines to Sapporo Service

Python により実行される [`run.sh`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/run.sh) スクリプトを参照してください。
この shell スクリプトは、例えば `cwltool` をワークフローエンジンとしてリクエストされた場合、`run_cwltool` の bash 関数を呼び出します。

この関数では、ワークフローエンジンを起動するのために、Docker コマンドを実行し、Docker プロセス終了を監視します。
完全な例については、このプルリクエストを参照してください <https://github.com/sapporo-wes/sapporo-service/pull/29>

## License

[Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).
See the [LICENSE](https://github.com/sapporo-wes/sapporo-service/blob/main/LICENSE).
