# SAPPORO-service

SAPPORO-service is a REST API Server that executes batch jobs. The REST API definition conforms to [GA4GH Workflow Execution Service API](https://github.com/ga4gh/workflow-execution-service-schemas).

[Japanese Document](https://hackmd.io/s/Skp49g2IN)

## Usage

Use a script that wraps docker-compose.

```shell
$ ./sapporo-service up
Start SAPPORO-service up...

  Debug              : False
  Port               : 1122
  Log Level          : INFO
  Get Runs           : True
  Token Auth         : False

Creating sapporo-service-app ... done
Creating sapporo-service-web ... done

Please try:

    $ curl -X GET localhost:1122/service-info

Finish SAPPORO-service up...

$ curl -X GET localhost:1122/service-info
{
  "auth_instructions_url": "https://dummy_auth_instructions_url/",
  "contact_info_url": "https://dummy_contact_info_url/",
  "supported_wes_versions": [
    "v1.0.0"
  ],
  "workflow_engines": [
    {
      "engine_name": "cwltool",
      "engine_version": "1.0.20191022103248",
      "workflow_types": [
        {
          "language_type": "CWL",
          "language_version": "v1.0"
        },
        {
          "language_type": "CWL",
          "language_version": "v1.1"
        }
      ]
    }
  ]
}

```

### Manage script

```shell
$ ./sapporo-service --help
sapporo-service is a set of management commands for SAPPORO-service.

Usage:
  sapporo-service up [-p <PORT>] [-l DEBUG|INFO] [-d --debug] [--disable-get-runs] [--enable-token-auth] [-h]
  sapporo-service down
  sapporo-service clean
  sapporo-service token [-h]
  sapporo-service token generate
  sapporo-service token show
  sapporo-service dev (up|down|clean|freeze|build|test) [-h]

Option:
  -h, --help                  Print usage.
  -v, --version               Print version.
```

### REST API Definition

It is described in the Swagger format in `./api-definition/SAPPORO-service-api-definition.yml`. Please confirm by the following method.

- [SAPPORO - Swagger UI](https://ddbj.github.io/SAPPORO-service/api-definition/swagger-ui/)

#### GET /service-info

`GET /service-info` is a REST API method for users to get the details of the service.

```shell
$ curl -X GET localhost:1122/service-info
{
  "auth_instructions_url": "https://dummy_auth_instructions_url/",
  "contact_info_url": "https://dummy_contact_info_url/",
  "supported_wes_versions": [
    "v1.0.0"
  ],
  "workflow_engines": [
    {
      "engine_name": "cwltool",
      "engine_version": "1.0.20191022103248",
      "workflow_types": [
        {
          "language_type": "CWL",
          "language_version": "v1.0"
        },
        {
          "language_type": "CWL",
          "language_version": "v1.1"
        }
      ]
    }
  ]
}
```

You can change the contents of response by editing `./service-info.yml`

#### GET /runs

Using `GET /runs`, can check all batch jobs in SAPPORO-service. However, when using SAPPORO-service by an unspecified number of users, problems arises (e.g. cancelling other user's batch jobs). The default setting is enable, so if you want to change this, start SAPPORO-service like `./sapporo-service up --disable-get-runs`.

#### POST /runs

Using `POST /runs`, can submit the batch job into SAPPORO-service. Examples of using curl and SAPPORO-fileserver follows:

```
$ cat test_jobs/trimming-and-qc-upload.yml
s3_upload_dir: cwl_upload # default value of type "string".
s3_bucket: sapporo # type "string"
nthreads: 10 # default value of type "int". (optional)
fastq: # type "File"
  class: File
  location: http://sapporo-fileserver-input:8080/small.ERR034597_1.fastq
endpoint: sapporo-fileserver-output:8080 # default value of type "string".
aws_secret_access_key: 01a603c1554b0b80ff02f4949e384e4f # type "string"
aws_access_key_id: ebd3fc49d00fcbf98efb64e07f68ad25 # type "string"

$ curl -X POST -F workflow_name=trimming_and_qc -F execution_engine_name=cwltool -F workflow_parameters=@test_jobs/trimming-and-qc-upload.yml localhost:1122/runs
{
  "run_id": "59bff94c-5cc4-4408-8d87-fee66ea91356",
  "status": "PENDING"
}

$ curl -X GET localhost:1122/runs
[
  {
    "run_id": "59bff94c-5cc4-4408-8d87-fee66ea91356",
    "status": "COMPLETE"
  }
]
```

#### GET /runs/\${run_id}

Using `GET /runs/${run_id}`, can fetch job informations such as status and stdout.

```shell
$ curl localhost:1122/runs/59bff94c-5cc4-4408-8d87-fee66ea91356
{
  "end_time": "2019-11-18 22:22:25",
  "execution_engine_name": "cwltool",
  "execution_engine_version": "1.0.20191022103248",
  "language_type": "CWL",
  "language_version": "v1.1",
  "run_id": "59bff94c-5cc4-4408-8d87-fee66ea91356",
  "start_time": "2019-11-18 22:22:11",
  "status": "COMPLETE",
  ...
}
```

### Add Workflow

You can add workflows by editing `./workflow-info.yml`

```shell
workflows:
  - workflow_name: trimming_and_qc
    workflow_version: v1.0.0
    workflow_location: https://raw.githubusercontent.com/ddbj/SAPPORO_test_workflow/master/workflow/trimming-and-qc/trimming-and-qc-upload/trimming-and-qc-upload.cwl
    workflow_parameters_template_location: https://raw.githubusercontent.com/ddbj/SAPPORO_test_workflow/master/workflow/trimming-and-qc/trimming-and-qc-upload/trimming-and-qc-upload.yml
    language_type: CWL
    language_version: v1.1
  - workflow_name: bwa_mapping_pe
    workflow_version: v1.0.0
    workflow_location: https://raw.githubusercontent.com/ddbj/SAPPORO_test_workflow/master/workflow/bwa-mapping-pe/bwa-mapping-pe-upload/bwa-mapping-pe-upload.cwl
    workflow_parameters_template_location: https://raw.githubusercontent.com/ddbj/SAPPORO_test_workflow/master/workflow/bwa-mapping-pe/bwa-mapping-pe-upload/bwa-mapping-pe-upload.yml
    language_type: CWL
    language_version: v1.1
```

The explanation of each item is as follows.

- workflow_name
    - Describe freely
    - Uniquely naming in `workflow.yml`
- workflow_version
    - Describe freely
    - In the example, writing git commit ID
- workflow_location
    - Describe the location of the workflow file
- workflow_parameters_template_location
    - Describe the location of the workflow execution parameters template file
- language*[type|version]
    - Specify language*[type|version] described in `service-info.yml`

---

Executable workflows have input/output parameter restrictions. Please check [GitHub - SAPPORO_test_workflow](https://github.com/ddbj/SAPPORO_test_workflow) as an example.

- Input data and workflow files must be hosted on the web
      - If you want to use local files, you need to prepare a file server
      - [SAPPORO-fileserver - README](https://github.com/ddbj/SAPPORO-fileserver/blob/master/README.md)
- Output data needs to be uploaded to file server or object storage
    - Write one line in `upload_url.txt` in the execution directory
    - The following are available as local object storage
    - [SAPPORO-fileserver - README](https://github.com/ddbj/SAPPORO-fileserver/blob/master/README.md)

### Manage Workflow Execution Engine, Job Scheduler

The workflow execution engine and job scheduler are abstracted in `./src/run_workflow.sh`.

```shell
#!/bin/bash

function run_wf() {
  if [[ ${execution_engine} == "cwltool" ]]; then
    run_cwltool
  elif [[ ${execution_engine} == "nextflow" ]]; then
    run_nextflow
  elif [[ ${execution_engine} == "toil" ]]; then
    run_toil
  fi
}

function run_cwltool() {
  echo "RUNNING" >$status
  cwltool --custom-net=sapporo-network --outdir $run_dir $workflow $workflow_parameters 1>$stdout 2>$stderr || echo "EXECUTOR_ERROR" >$status
  echo "COMPLETE" >$status
  exit 0
}
```

First, to install the workflow execution engine and the job scheduler in the Docker container. Edit `./Dockerfile` and rebuild it, or enter container `docker-compose exec app bash` and install directly. Then edit `./src/run_workflow.sh` and `./service-info.yml`.

### Network

SAPPORO-service is using Flask. The network configuration is as follows.

```text
Flask <-> uwsgi <-(uWSGI protocol)-> Nginx <-(HTTP)-> Docker <-> User
```

As an initial setting, Nginx provides `localhost:1122` as a REST API endpoint. If you want to change the port, start SAPPORO-service like `./sapporo-service up --port ${PORT_NUM}`.

If you want to use SSL/TSL, edit `./etc/nginx/nginx.conf`.

### Logging

The following items are output as logs.

```shell
$ ls ./log
app  nginx
```

To change the log level, start SAPPORO-service like `./sapporo-service up --log-level DEBUG`. When set as `DEBUG`, traceback of Python is displayed in `./log/app/flask.log`.

If you want log rotation of `./log/app/flask.log`., edit `./src/app/logging_config.py`.

### Token authentication

SAPPORO-service can use simple token authentication. Start SAPPORO-service like `./sapporo-service up --enable-token-auth`.

```shell
$ curl -X GET localhost:1122/service-info
{
  "msg": "Unauthorized.",
  "status_code": 401
}
```

To issue a token, using `./sapporo-service token generate`.

```shell
$ ./sapporo-service token generate
Generated token:

    b50c1ada5207b445e8e0e33567405c87
```

The tokens are recorded in `.src/app/token_list.txt` in a line break delimited format. If you want to revoke, please edit this file.

```shell
$ ./sapporo-service token show
Token list:

    b50c1ada5207b445e8e0e33567405c87
```

Token authentication is done by adding the `Authorization` header to the request.

```shell
$ curl -H 'Authorization:b50c1ada5207b445e8e0e33567405c87' localhost:1122/service-info
{
  "auth_instructions_url": "https://dummy_auth_instructions_url/",
  "contact_info_url": "https://dummy_contact_info_url/",
  "supported_wes_versions": [
    "v1.0.0"
  ],
  "workflow_engines": [
    {
      "engine_name": "cwltool",
      "engine_version": "1.0.20181201184214",
      "workflow_types": [
        {
          "language_type": "CWL",
          "language_version": "v1.0"
        }
      ]
    }
  ]
}
```

When using token authentication, it is necessary to encrypt the header, so please use SSL/TLS.

## Development

### Build and Docker push

```shell
./sapporo-service dev freeze
./sapporo-service dev build ${VERSION}
docker push suecharo/sapporo-service:${VERSION}
```
