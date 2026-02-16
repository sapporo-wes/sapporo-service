# Dockerfile for Workflow Engines

## Why?

The official `broadinstitute/cromwell` image does not include Docker CLI.
Cromwell needs Docker CLI to execute WDL tasks with `runtime { docker: "..." }`.

Sapporo runs workflow engines inside Docker containers via DinD (Docker-in-Docker), mounting the host Docker socket (`/var/run/docker.sock`) into the engine container.
For Cromwell to spawn task containers through this socket, it must have Docker CLI installed.

This directory contains a custom Dockerfile that installs Docker CE CLI on top of the official Cromwell image.

## Cromwell

Build and push:

```bash
docker build -f ./Dockerfile-cromwell -t ghcr.io/sapporo-wes/cromwell-with-docker:92 .
docker push ghcr.io/sapporo-wes/cromwell-with-docker:92
```

When upgrading Cromwell, update the tag in both `Dockerfile-cromwell` (`FROM` line) and `sapporo/run.sh` (`run_cromwell()` function).
