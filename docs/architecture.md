# Architecture

## System Overview

The sapporo-service is a FastAPI application that accepts WES API requests, prepares a run directory for each workflow execution, and delegates the actual workflow engine invocation to a shell script (`run.sh`). Each workflow engine runs inside its own Docker container, spawned as a sibling container via the host's Docker socket. See [Installation - Volume Mounts](installation.md#volume-mounts-docker-in-docker) for details on the DinD volume mount requirements.

```text
         +-----------+
         |  Client   |
         +-----------+
               |
          HTTP request
               |
               v
         +-----------+
         |  FastAPI  |
         +-----------+
               |
         Python call
               |
               v
         +-----------+
         |  run.py   |
         +-----------+
               |
          subprocess
               |
               v
         +-----------+
         |  run.sh   |
         +-----------+
               |
          docker run
               |
               v
         +-----------+
         |  Engine   |
         | Container |
         +-----------+
```

The Python side (`run.py`) never calls a workflow engine directly. It prepares the run directory, writes all input files, then forks `run.sh` as a subprocess. All run data is persisted to the filesystem, with a SQLite index for fast listing.

## run.sh: Workflow Engine Abstraction

The [`run.sh`](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo/run.sh) script is the single interface between the sapporo-service (Python) and all workflow engines. It dispatches to a `run_<engine>()` function based on the `workflow_engine` field in the run request.

Each engine function constructs a `docker run` command that:

1. Mounts the Docker socket (`-v /var/run/docker.sock:...`) so that the engine can start one container per workflow step (all engines except snakemake, which runs its steps inside its own container)
2. Mounts the run directory (`-v ${run_dir}:${run_dir}`)
3. Sets the working directory to the execution directory (`-w=${exe_dir}`)
4. Runs the engine-specific command with the workflow URL and parameters

Override the default `run.sh` location using `--run-sh` or `SAPPORO_RUN_SH`. See [Configuration - Custom run.sh](configuration.md#custom-runsh) for details.

### Engine Dispatch

`run.sh` uses a naming convention to dispatch to the correct engine function. For a request with `"workflow_engine": "cwltool"`, it calls `run_cwltool()`. If no matching function exists, the run fails with `EXECUTOR_ERROR`.

### Cancellation

`run.sh` runs the workflow function as a background job in its own process group (`set -m`) and waits for it, so that the parent process stays free to handle signals. `POST /runs/{run_id}/cancel` writes `CANCELING` to `state.txt` and sends `SIGUSR1` to the `run.sh` process. The signal handler then:

1. Calls `cancel()`, which runs `cancel_docker_engine()`, then the engine-specific hook `cancel_<engine>()` if that function is defined, and then `stop_run_wf()`
2. `cancel_docker_engine()` kills the engine container: the bundled `run_<engine>()` functions pass `--cidfile` to `docker run`, and the recorded id is used only if that container was started for this run's `exe/` directory
3. `stop_run_wf()` sends `SIGTERM` to the process group of the background job, waits up to `--cancel-grace-seconds` (default 30 seconds), and then sends `SIGKILL` to the group
4. Writes exit code `138` and the `CANCELED` state

The process group contains the engine process and everything it started on this host. An attached `docker run`, `podman run` or `srun` forwards `SIGTERM` to what it runs, but an engine inside a container does not always exit on it, and the container outlives the `docker run` client; this is why the bundled engines also kill the container by id. Work that lives elsewhere, such as a Slurm job submitted with `sbatch` or containers that the engine itself started through the Docker socket for workflow steps, is not reached. Put that cleanup into `cancel_<engine>()`.

Once the parent process has written `CANCELING` or `SYSTEM_ERROR`, the background job does not write a terminal state anymore. A workflow that ends after the cancel therefore cannot turn the run back into `COMPLETE` or `EXECUTOR_ERROR`. If `state.txt` already says `CANCELING` when `run.sh` starts, it writes `CANCELED` without starting the engine.

A run in `INITIALIZING` has no `run.sh` process yet: the service is still downloading its attachments. A cancel in this phase writes `CANCELING`, the download stops before the next attachment, and the run becomes `CANCELED` with exit code `138` without starting `run.sh`. A delete in this phase removes the run directory contents in the same way, and whatever the download wrote after the deletion is removed again when the download stops.

### Error Handling

`run.sh` uses `trap` to handle errors and signals. `set -E` makes the `ERR` trap apply inside functions and inside the background job as well.

- `ERR` -> `SYSTEM_ERROR` (unexpected failure in `run.sh` itself, such as a failed `mkdir` or `cp`)
- `SIGHUP/SIGINT/SIGQUIT/SIGTERM` -> `SYSTEM_ERROR` (killed by system; the engine is stopped in the same way as on cancel)
- Unknown signals -> `SYSTEM_ERROR` with exit code 1 (catch-all)
- `USR1` -> `CANCELED` (user-requested cancellation)
- Non-zero exit from a `run_<engine>()` function -> `EXECUTOR_ERROR`

RO-Crate metadata is generated on the `COMPLETE` and `EXECUTOR_ERROR` paths. For `EXECUTOR_ERROR`, the RO-Crate uses `FailedActionStatus` and may have no output files. If RO-Crate generation itself fails, `run.sh` writes `{"@error": "RO-Crate generation failed. Check stderr.log for details."}` to `ro-crate-metadata.json` and appends the Python error traceback to `stderr.log`. The `SYSTEM_ERROR` and `CANCELED` paths skip RO-Crate generation because their preconditions (e.g., run request, start time) may not be satisfied.

### Adding a New Engine

To add a new workflow engine, define a `run_<engine>()` function in `run.sh` that constructs the appropriate `docker run` command. The function must:

1. Build a `docker run` command that mounts the Docker socket and run directory
2. Pass the command array to `_write_and_run()`, which writes the command to `${cmd}`, runs it with stdout/stderr redirected to `${stdout}` and `${stderr}`, and calls `executor_error $?` on non-zero exit

Pass `--cidfile "${engine_cid}"` to `docker run` so that `cancel_docker_engine()` can kill the container. If cancel needs more than that (for example `scancel` for a Slurm job, or stopping containers the engine started for its steps), define `cancel_<engine>()`. `cancel()` calls it before stopping the process group.

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
│       ├── multiqc_general_stats.json
│       ├── outputs/
│       │   └── <output_file>
│       ├── outputs.json
│       ├── README.md
│       ├── ro-crate-metadata.json
│       ├── run.pid
│       ├── run_request.json
│       ├── runtime_info.json
│       ├── start_time.txt
│       ├── state.txt
│       ├── stderr.log
│       ├── stdout.log
│       ├── system_logs.json
│       ├── username.txt
│       └── workflow_engine_params.txt
├── 2d/
│   └── ...
└── sapporo.db
```

### File Descriptions

| File | Description |
|---|---|
| `run_request.json` | Original run request (workflow URL, engine, parameters) |
| `username.txt` | Owner of the run. Written when authentication is enabled |
| `state.txt` | Current run state (e.g., `RUNNING`, `COMPLETE`). Read as `UNKNOWN` when the file is missing or does not contain a valid state |
| `exe/` | Execution directory (working directory for the workflow engine) |
| `exe/workflow_params.json` | Workflow parameters |
| `outputs/` | Output files produced by the workflow |
| `outputs.json` | JSON listing of output files |
| `cmd.txt` | The `docker run` command that was executed |
| `stdout.log` / `stderr.log` | Workflow engine stdout/stderr |
| `start_time.txt` / `end_time.txt` | ISO 8601 timestamps |
| `exit_code.txt` | Process exit code |
| `run.pid` | PID of the `run.sh` subprocess. A value of 1 or less is ignored |
| `runtime_info.json` | Runtime metadata |
| `system_logs.json` | System-level logs |
| `workflow_engine_params.txt` | Engine-specific parameters |
| `ro-crate-metadata.json` / `README.md` | RO-Crate metadata and its README, written after the run ends (see [RO-Crate](ro-crate.md)) |
| `multiqc_general_stats.json` | MultiQC statistics, written during RO-Crate generation when MultiQC finds supported tool outputs |

## Reconciliation

Detects runs stuck in `RUNNING`/`QUEUED` after a process restart and marks them as `SYSTEM_ERROR`.

`reconcile_runs()` runs at startup (before `init_db()`) and periodically in the background (at the snapshot interval, default: 30 minutes). For each run in a non-terminal state, it reads `run.pid` and checks whether that process is still the `run.sh` of this run. The check reads `/proc/<pid>/cmdline` and requires the run directory to appear in it, so a PID that the system reused for another process (for example after a container restart) does not count as alive.

| PID file | run.sh alive | Action |
|---|---|---|
| Present | Yes | Skip (running normally) |
| Present | No | Set `SYSTEM_ERROR` (reason: "process vanished") |
| Absent | N/A | Set `SYSTEM_ERROR` (reason: "no pid file") |

Runs in terminal states (`COMPLETE`, `EXECUTOR_ERROR`, `SYSTEM_ERROR`, `CANCELED`, `DELETED`) and `UNKNOWN` are skipped. For each reconciled run, `state.txt` is set to `SYSTEM_ERROR`, the current timestamp is written to `end_time.txt`, and the reason is logged to `system_logs.json`.

`INITIALIZING` runs whose attachments this process is still downloading have no `run.pid` yet and are skipped by the periodic reconciliation. At startup, every `INITIALIZING` run is reconciled, because no download survives a restart.

A run whose files cannot be processed (for example a `system_logs.json` that is not a list) is logged and skipped. One broken run directory does not stop reconciliation or server startup.

## SQLite Index

The SQLite database (`sapporo.db`) is an **index**, not a data store. A background asyncio task syncs it with the run directories at a configurable interval (default: 30 minutes), and it can be deleted at any time without data loss. `GET /runs` uses it to filter, sort and paginate; with the default `latest=true` the state of each listed run is then read from its run directory, and with `latest=false` the indexed snapshot is returned as is. `system_state_counts` in `GET /service-info` is also counted from the index. Individual run queries (`GET /runs/{run_id}`) always read from the filesystem.

Each sync adds runs that are new on disk, removes rows whose run directory is gone, and refreshes rows that are not in a terminal state or whose `state.txt` differs from the index. `POST /runs` and `DELETE /runs/{run_id}` update the index immediately; the periodic sync covers the state changes that `run.sh` makes.

A deleted run keeps `state.txt`, `start_time.txt`, `end_time.txt` and `username.txt`, so it stays in the index as `DELETED`: it appears in `GET /runs`, in `GET /runs?state=DELETED`, and in `system_state_counts`, and its owner can still read its status. Automatic cleanup (`--run-remove-older-than-days`) does not pick up runs that are already `DELETED`.

A run whose directory cannot be parsed (for example a missing `start_time.txt`) is logged and left out of the index. The run stays accessible through `GET /runs/{run_id}`. An error inside a background loop is logged and the loop continues.

## RO-Crate

After each run completes (or fails at the executor level), the service generates [RO-Crate](https://www.researchobject.org/ro-crate/) metadata (`ro-crate-metadata.json`). See [RO-Crate](ro-crate.md) for the full specification including conformance profiles, entity graph, custom properties, bioinformatics extensions, and validation.
