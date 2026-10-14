# Configuration

## CLI Options

```text
sapporo --help
usage: sapporo [-h] [--host str] [--port int] [--debug] [--run-dir PATH]
               [--service-info PATH] [--executable-workflows PATH]
               [--run-sh PATH] [--url-prefix str] [--base-url str]
               [--allow-origin str] [--auth-config PATH]
               [--run-remove-older-than-days int]
               [--snapshot-interval int] [--cancel-grace-seconds int]

options:
  -h, --help                       show this help message and exit
  --host str                       Host address for the service
                                   (default: 127.0.0.1)
  --port int                       Port number for the service
                                   (default: 1122)
  --debug                          Enable debug mode (default: False)
  --run-dir PATH                   Directory where the runs are stored
                                   (default: ./runs)
  --service-info PATH              Path to the service_info.json file
  --executable-workflows PATH      Path to the executable_workflows.json file
  --run-sh PATH                    Path to the run.sh script
  --url-prefix str                 URL prefix for the service endpoints
                                   (default: '', e.g., /sapporo/api)
  --base-url str                   Base URL for downloading the output files
                                   of the executed runs
                                   (default: http://{host}:{port}{url_prefix})
  --allow-origin str               Access-Control-Allow-Origin header value
                                   (default: *)
  --auth-config PATH               Path to the auth_config.json file
  --run-remove-older-than-days int Clean up run directories with a start time
                                   older than the specified number of days
                                   (must be >= 1)
  --snapshot-interval int          Interval in minutes for DB snapshot
                                   rebuilds and cleanup jobs (must be >= 1,
                                   default: 30)
  --cancel-grace-seconds int       Seconds between SIGTERM and SIGKILL when
                                   a run is canceled (must be >= 0,
                                   default: 30)
```

## Environment Variables

All CLI options can be set via environment variables with the `SAPPORO_` prefix:

| CLI Option | Environment Variable | Default |
|---|---|---|
| `--host` | `SAPPORO_HOST` | `127.0.0.1` (`0.0.0.0` inside Docker) |
| `--port` | `SAPPORO_PORT` | `1122` |
| `--debug` | `SAPPORO_DEBUG` | `False` |
| `--run-dir` | `SAPPORO_RUN_DIR` | `./runs` |
| `--service-info` | `SAPPORO_SERVICE_INFO` | Built-in default |
| `--executable-workflows` | `SAPPORO_EXECUTABLE_WORKFLOWS` | Built-in default |
| `--run-sh` | `SAPPORO_RUN_SH` | Built-in default |
| `--url-prefix` | `SAPPORO_URL_PREFIX` | `""` |
| `--base-url` | `SAPPORO_BASE_URL` | `http://{host}:{port}{url_prefix}` |
| `--allow-origin` | `SAPPORO_ALLOW_ORIGIN` | `*` |
| `--auth-config` | `SAPPORO_AUTH_CONFIG` | Built-in default |
| `--run-remove-older-than-days` | `SAPPORO_RUN_REMOVE_OLDER_THAN_DAYS` | None |
| `--snapshot-interval` | `SAPPORO_SNAPSHOT_INTERVAL` | `30` |
| `--cancel-grace-seconds` | `SAPPORO_CANCEL_GRACE_SECONDS` | `30` |
| - | `SAPPORO_EXTRA_DOCKER_ARGS` | (unset) |

`SAPPORO_EXTRA_DOCKER_ARGS` holds additional `docker run` flags for the workflow engine containers, separated by spaces. The bundled `run.sh` reads it in `set_extra_docker_args()` and passes the flags to the engine container of every run, for every engine. Use it to mount host directories that workflows read, or to limit the resources of the engine container.

```bash
# Example: mount a single directory
SAPPORO_EXTRA_DOCKER_ARGS="-v /data:/data"

# Example: mount multiple directories
SAPPORO_EXTRA_DOCKER_ARGS="-v /data:/data -v /ref:/ref"

# Example: limit the memory, the CPUs and the number of processes of the engine container
SAPPORO_EXTRA_DOCKER_ARGS="--memory 8g --cpus 4 --pids-limit 1024"
```

The flags apply to the engine container only. Containers that the engine starts for workflow steps through the Docker socket do not get them, so limit those through the configuration of the engine. To choose the flags for each run, for example to mount only the data that one workflow may read, edit `set_extra_docker_args()` in a [custom run.sh](#custom-runsh). The function can decide by `${wf_engine}`, `${wf_url}` and the owner of the run in `${run_dir}/username.txt`.

`--cancel-grace-seconds` is passed to `run.sh` as `SAPPORO_CANCEL_GRACE_SECONDS`. When a run is canceled or `run.sh` is shut down, the engine container is stopped with `docker stop` and the process group of the engine receives `SIGTERM`. The engine has this many seconds to stop the containers it started for workflow steps and to exit before it receives `SIGKILL`. See [Architecture - Cancellation](architecture.md#cancellation).

Priority: CLI arguments > Environment variables > Default values.

## service_info.json

Customize the response of `GET /service-info` by providing a JSON file via `--service-info`. The default is bundled at `sapporo/service_info.json`.

The file is **partially merged** with built-in defaults: fields present in the file override the defaults, while missing fields fall back to built-in values. This means you only need to specify the fields you want to customize.

`POST /runs` rejects `workflow_engine_parameters` that contain `;`, `|`, `&`, `$`, `` ` ``, `(`, `)`, `{`, `}`, `!`, a newline, a carriage return or a NUL character. The `name` and `default_value` of `default_workflow_engine_parameters` must not contain these characters either, because `run.sh` receives the defaults in the same way. If a default contains one of them, sapporo does not start.

## executable_workflows.json

Restrict which workflows can be executed using `--executable-workflows` or `SAPPORO_EXECUTABLE_WORKFLOWS`.

Format:

```json
{
  "workflows": [
    "https://example.com/workflow.cwl"
  ]
}
```

- An empty array allows all workflows. `workflow_engine_parameters` in `POST /runs` are then passed to the engine as given, apart from the characters listed in [service_info.json](#service_infojson). The submitter therefore also chooses the engine options, including options that weaken the isolation of the run, such as `--no-container` of cwltool. To restrict them, list the workflows.
- Each URL must be a remote resource (http/https).
- Any `workflow_url` in `POST /runs` must match this list or the request returns a 400 Bad Request error.
- While the list is not empty, `workflow_engine_parameters` in `POST /runs` is rejected with 400 Bad Request. Every run uses the `default_workflow_engine_parameters` of `service_info.json`, so a registered workflow runs only with the parameters that the administrator chose. Engine parameters could otherwise point the engine at another workflow or configuration file.
- `workflow_attachment` and `workflow_attachment_obj` stay available for input files. Whether a registered workflow reads a file from the attachments is decided by the workflow itself, so register only workflows that you trust.
- Query available workflows via `GET /executable-workflows`.

## Custom run.sh

Override the default `run.sh` script using `--run-sh` or `SAPPORO_RUN_SH`. This allows you to customize how workflow engines are invoked, add environment-specific upload or cleanup logic, or integrate new engines without modifying the bundled script. See [Architecture - run.sh](architecture.md#runsh-workflow-engine-abstraction) for details on the script structure.

## Supported Engine / Workflow Type Combinations

The sapporo API validates engines and workflow types independently, but only
certain combinations actually work at runtime. The default `run.sh` supports
the following:

| Engine | Workflow Type | Container Image | Notes |
|---|---|---|---|
| cwltool | CWL | `quay.io/commonwl/cwltool:3.3.20260925135507` | |
| toil | CWL | `quay.io/ucsc_cgl/toil:9.5.0` | A cancel does not stop the containers that toil started for workflow steps |
| ep3 | CWL | `ghcr.io/tom-tan/ep3:v1.7.0` | A cancel does not stop the containers that ep3 started for workflow steps |
| cromwell | WDL | `ghcr.io/sapporo-wes/cromwell-with-docker:92` | CWL support was removed in Cromwell 85 |
| nextflow | NFL | `nextflow/nextflow:26.10.0` | |
| snakemake | SMK | `snakemake/snakemake:v9.27.0` | |
| streamflow | CWL | `alphaunito/streamflow:0.2.0rc3` | Pre-release; uses cwl-runner interface. A cancel does not stop the containers that StreamFlow started for workflow steps |

## Output File Download

- List output files: `GET /runs/{run_id}/outputs`
- Download all outputs as zip: `GET /runs/{run_id}/outputs?download=true`
- Download a specific file: `GET /runs/{run_id}/outputs/{path}`
- Configure the base URL for downloads using `--base-url` or `SAPPORO_BASE_URL`. Files are accessible at `{base_url}/runs/{run_id}/outputs/{path}`.
- File names are used as the engine wrote them, so every output can be addressed. `file_url` in the outputs list percent-encodes the path.
- A symlink in `outputs/` is served when its target is inside the run directory (for example a Nextflow `publishDir` in `symlink` mode, which points into the work directory under `exe/`). A symlink to a directory is followed by the same rule, so the files inside it appear in the outputs list, in the ZIP download and in the RO-Crate. A symlink whose target is outside the run directory is rejected with 400 and left out of the ZIP download and the RO-Crate.

## Run Cleanup

Automatically remove old run directories using `--run-remove-older-than-days` or `SAPPORO_RUN_REMOVE_OLDER_THAN_DAYS`. The service periodically cleans up runs with a start time older than the specified number of days. The value must be an integer greater than or equal to 1; specifying `0` raises a `ValueError`.

## Logging

### Output

All log messages are written to **stderr**. Standard output is not used for logging.

### Format

```text
2025-01-01 12:00:00 INFO     sapporo.run - Starting workflow run
```

Format string: `%(asctime)s %(levelprefix)s %(name)s - %(message)s`

### Log Level

Controlled by the `--debug` flag (or `SAPPORO_DEBUG`):

| Flag | Root level | SQLAlchemy level |
|---|---|---|
| Off (default) | INFO | WARNING |
| `--debug` | DEBUG | INFO |
