# Configuration

## CLI Options

```text
sapporo --help
usage: sapporo [-h] [--host] [--port] [--debug] [--run-dir] [--service-info]
               [--executable-workflows] [--run-sh] [--url-prefix] [--base-url]
               [--allow-origin] [--auth-config] [--run-remove-older-than-days]

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

## Environment Variables

All CLI options can be set via environment variables with the `SAPPORO_` prefix:

| CLI Option | Environment Variable | Default |
|---|---|---|
| `--host` | `SAPPORO_HOST` | `127.0.0.1` |
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

Priority: CLI arguments > Environment variables > Default values.

## service_info.json

Customize the response of `GET /service-info` by providing a JSON file via `--service-info`. The default is bundled at `sapporo/service_info.json`.

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

- An empty array allows all workflows.
- Each URL must be a remote resource (http/https).
- Any `workflow_url` in `POST /runs` must match this list or the request returns a 400 Bad Request error.
- Query available workflows via `GET /executable_workflows`.

## Custom run.sh

Override the default `run.sh` script using `--run-sh` or `SAPPORO_RUN_SH`. This allows you to customize how workflow engines are invoked, add environment-specific upload or cleanup logic, or integrate new engines without modifying the bundled script. See [Architecture - run.sh](architecture.md#runsh-workflow-engine-abstraction) for details on the script structure.

## Output File Download

- List output files: `GET /runs/{run_id}/outputs`
- Download all outputs as zip: `GET /runs/{run_id}/outputs?download=true`
- Download a specific file: `GET /runs/{run_id}/outputs/{path}`
- Configure the base URL for downloads using `--base-url` or `SAPPORO_BASE_URL`. Files are accessible at `{base_url}/runs/{run_id}/outputs/{path}`.

## Run Cleanup

Automatically remove old run directories using `--run-remove-older-than-days` or `SAPPORO_RUN_REMOVE_OLDER_THAN_DAYS`. The service periodically cleans up runs with a start time older than the specified number of days.
