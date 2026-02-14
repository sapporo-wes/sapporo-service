# Getting Started

This guide walks you through starting the sapporo-service, submitting a workflow, and retrieving the results.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (Docker Compose V2 included)
- [curl](https://curl.se/) and [jq](https://jqlang.github.io/jq/) for command-line interaction

## Start the Service

Clone the repository and start the service with Docker Compose:

```bash
git clone https://github.com/sapporo-wes/sapporo-service.git
cd sapporo-service
docker compose up -d
```

## Verify the Service

Confirm the service is running:

```bash
curl -fsSL localhost:1122/service-info | jq .
```

The response includes the service name, supported workflow engines, and API version.

## Submit a Workflow

Submit a [CWL](https://www.commonwl.org/) workflow that runs quality control on paired-end FASTQ files using cwltool:

```bash
curl -fsSL -X POST \
  -F "workflow_type=CWL" \
  -F "workflow_url=https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/trimming_and_qc_remote.cwl" \
  -F 'workflow_params={
    "fastq_1": {
      "class": "File",
      "location": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/ERR034597_1.small.fq.gz"
    },
    "fastq_2": {
      "class": "File",
      "location": "https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/tests/resources/cwltool/ERR034597_2.small.fq.gz"
    }
  }' \
  -F "workflow_engine=cwltool" \
  localhost:1122/runs | jq .
```

The response contains a `run_id`:

```json
{
  "run_id": "29109b85-7935-4e13-8773-9def402c7775"
}
```

## Check Run Status

Poll the run status using the `run_id` from the previous step:

```bash
curl -fsSL localhost:1122/runs/${RUN_ID}/status | jq .
```

The run progresses through these states: `QUEUED` -> `INITIALIZING` -> `RUNNING` -> `COMPLETE`. See [API Specification - Run States](api-spec.md#run-states) for the full state list.

Retrieve the full run details:

```bash
curl -fsSL localhost:1122/runs/${RUN_ID} | jq .
```

## Retrieve Outputs

Once the run reaches `COMPLETE`, list the output files:

```bash
curl -fsSL localhost:1122/runs/${RUN_ID}/outputs | jq .
```

Download all outputs as a zip archive:

```bash
curl -fsSL -o outputs.zip "localhost:1122/runs/${RUN_ID}/outputs?download=true"
```

Download a specific output file:

```bash
curl -fsSL -o result.html "localhost:1122/runs/${RUN_ID}/outputs/qc_result_1.html"
```

## Next Steps

- [Installation](installation.md) - Install with pip, configure Docker volume mounts
- [Configuration](configuration.md) - Customize CLI options, restrict executable workflows
- [Authentication](authentication.md) - Enable JWT authentication
- [API Specification](api-spec.md) - Full endpoint reference and request/response examples
