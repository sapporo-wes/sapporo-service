# Architecture

## System Overview

The sapporo-service is a FastAPI application that accepts WES API requests, prepares a run directory for each workflow execution, and delegates the actual workflow engine invocation to a shell script (`run.sh`). Each workflow engine runs inside its own Docker container, spawned as a sibling container via the host's Docker socket. See [Installation - Volume Mounts](installation.md#volume-mounts-docker-in-docker) for details on the DinD volume mount requirements.

```text
+--------+     +---------+     +--------+     +---------------------+
| Client | --> | FastAPI | --> | run.py | --> | run.sh (subprocess) |
+--------+     +---------+     +--------+     +---------------------+
                                                   |
                                              docker run
                                                   |
                                             +------------+
                                             | Engine     |
                                             | Container  |
                                             +------------+
```

The Python side (`run.py`) never calls a workflow engine directly. It prepares the run directory, writes all input files, then forks `run.sh` as a subprocess. All run data is persisted to the filesystem, with a SQLite index for fast listing.

## run.sh: Workflow Engine Abstraction

The [`run.sh`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/run.sh) script is the single interface between the sapporo-service (Python) and all workflow engines. It dispatches to a `run_<engine>()` function based on the `workflow_engine` field in the run request.

Each engine function constructs a `docker run` command that:

1. Mounts the Docker socket (`-v /var/run/docker.sock:...`)
2. Mounts the run directory (`-v ${run_dir}:${run_dir}`)
3. Sets the working directory to the execution directory (`-w=${exe_dir}`)
4. Runs the engine-specific command with the workflow URL and parameters

Override the default `run.sh` location using `--run-sh` or `SAPPORO_RUN_SH`. See [Configuration - Custom run.sh](configuration.md#custom-runsh) for details.

### Engine Dispatch

`run.sh` uses a naming convention to dispatch to the correct engine function. For a request with `"workflow_engine": "cwltool"`, it calls `run_cwltool()`. If no matching function exists, the run fails with `EXECUTOR_ERROR`.

### Cancellation

`run.sh` runs the workflow function as a background process and waits for it. Cancellation is handled via Unix signals: the Python side sends `SIGUSR1` to the `run.sh` process, which triggers the `cancel()` function. This allows engine-specific cleanup before writing the `CANCELED` state.

### Error Handling

`run.sh` uses `trap` to handle errors and signals:

- `ERR` -> `SYSTEM_ERROR` (unexpected failure)
- `SIGHUP/SIGINT/SIGQUIT/SIGTERM` -> `SYSTEM_ERROR` (killed by system)
- Unknown signals -> `SYSTEM_ERROR` with exit code 1 (catch-all)
- `USR1` -> `CANCELED` (user-requested cancellation)
- Non-zero exit from a `run_<engine>()` function -> `EXECUTOR_ERROR`

RO-Crate metadata is generated only on the success path (`COMPLETE` state). Error and cancellation paths (`SYSTEM_ERROR`, `EXECUTOR_ERROR`, `CANCELED`) skip RO-Crate generation because it is a heavyweight operation (Python startup, file hashing, optional Docker-based tools) and its preconditions may not be satisfied in error states.

### Adding a New Engine

To add a new workflow engine, define a `run_<engine>()` function in `run.sh` that constructs the appropriate `docker run` command. The function must:

1. Build a `docker run` command that mounts the Docker socket and run directory
2. Write the command to `${cmd}` for logging
3. Execute the command, redirecting stdout/stderr to `${stdout}` and `${stderr}`
4. Call `executor_error $?` on non-zero exit

For a complete example, see the [StreamFlow addition PR](https://github.com/sapporo-wes/sapporo-service/pull/29).

## Run Directory

Each workflow execution is stored on the filesystem at `{run_dir}/{run_id[:2]}/{run_id}/`. The run directory is the **single source of truth** for all run data.

### Directory Structure

```text
runs/
├── 29/
│   └── 29109b85-7935-4e13-8773-9def402c7775/
│       ├── cmd.txt
│       ├── end_time.txt
│       ├── exe/
│       │   └── workflow_params.json
│       ├── exit_code.txt
│       ├── outputs/
│       │   └── <output_file>
│       ├── outputs.json
│       ├── run.pid
│       ├── run_request.json
│       ├── runtime_info.json
│       ├── start_time.txt
│       ├── state.txt
│       ├── stderr.log
│       ├── stdout.log
│       ├── system_logs.json
│       └── workflow_engine_params.txt
├── 2d/
│   └── ...
└── sapporo.db
```

### File Descriptions

| File | Description |
|---|---|
| `run_request.json` | Original run request (workflow URL, engine, parameters) |
| `state.txt` | Current run state (e.g., `RUNNING`, `COMPLETE`) |
| `exe/` | Execution directory (working directory for the workflow engine) |
| `exe/workflow_params.json` | Workflow parameters |
| `outputs/` | Output files produced by the workflow |
| `outputs.json` | JSON listing of output files |
| `cmd.txt` | The `docker run` command that was executed |
| `stdout.log` / `stderr.log` | Workflow engine stdout/stderr |
| `start_time.txt` / `end_time.txt` | ISO 8601 timestamps |
| `exit_code.txt` | Process exit code |
| `run.pid` | PID of the `run.sh` subprocess |
| `runtime_info.json` | Runtime metadata |
| `system_logs.json` | System-level logs |
| `workflow_engine_params.txt` | Engine-specific parameters |

## SQLite Index

The SQLite database (`sapporo.db`) is an **index**, not a data store. It is rebuilt every 30 minutes by scanning the run directories and can be deleted at any time without data loss. It exists solely to make `GET /runs` (list all runs) fast. Individual run queries (`GET /runs/{run_id}`) always read from the filesystem.

## RO-Crate

After each run completes, the service generates [RO-Crate](https://www.researchobject.org/ro-crate/) metadata (`ro-crate-metadata.json`) following the Workflow Run Crate profile. This captures:

- Workflow document and parameters
- Input/output file references
- MultiQC quality statistics (when applicable)
- BAM/VCF file statistics via samtools/vcftools (when applicable)

RO-Crate generation is called from `run.sh` after the workflow engine completes, so it runs in the same subprocess as the workflow execution.
