# Installation

## Python Package

Requirements:

- Python 3.10 or later
- Docker (for running workflow engines)

Install from PyPI:

```bash
pip install sapporo
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install sapporo
```

## Starting the Server

Start the service:

```bash
sapporo
```

After startup, access `localhost:1122/docs` to view the API documentation through Swagger UI.

See [Configuration](configuration.md) for CLI options and environment variables.

## Docker

### Docker Image

The official Docker image is published at `ghcr.io/sapporo-wes/sapporo-service`. Multi-architecture images (amd64/arm64) are built by CI on each release.

```bash
# Specific version
docker pull ghcr.io/sapporo-wes/sapporo-service:2.1.0

# Latest
docker pull ghcr.io/sapporo-wes/sapporo-service:latest
```

### Docker Compose

Start the service with Docker Compose:

```bash
docker compose up -d
```

The `compose.yml` in the repository:

```yaml
services:
  app:
    image: ghcr.io/sapporo-wes/sapporo-service:${SAPPORO_VERSION:-latest}
    container_name: sapporo-service
    environment:
      - SAPPORO_HOST=0.0.0.0
      - SAPPORO_PORT=1122
      - SAPPORO_DEBUG=False
      - SAPPORO_RUN_DIR=${PWD}/runs
    volumes:
      - ${PWD}/runs:${PWD}/runs:rw
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - 127.0.0.1:1122:1122
    working_dir: /app
    command: ["sapporo"]
    networks:
      - sapporo-network
    init: true

networks:
  sapporo-network:
```

### Volume Mounts (Docker-in-Docker)

The sapporo-service does not install workflow engines directly. Instead, it runs each workflow engine inside a Docker container, communicating through the host's Docker socket (`/var/run/docker.sock`). This is called Docker-in-Docker (DinD), though technically the service spawns sibling containers (not nested ones) on the host Docker daemon.

The key constraint is that **volume mount paths must be identical between the host and the sapporo container**. When a workflow engine container mounts `${run_dir}:${run_dir}`, Docker resolves that path on the host filesystem. If the sapporo container used a different internal path, the workflow engine container would mount an empty or nonexistent directory.

This is why `compose.yml` uses `${PWD}/runs:${PWD}/runs` -- the host absolute path is passed through as-is, ensuring that both the sapporo container and any spawned workflow engine containers see the same files at the same paths. The three required mounts are:

1. **Docker socket** (`/var/run/docker.sock:/var/run/docker.sock`) -- allows the service to spawn workflow engine containers
2. **Run directory** (`${PWD}/runs:${PWD}/runs`) -- uses the host absolute path so paths match between containers
3. **`SAPPORO_RUN_DIR`** (`${PWD}/runs`) -- tells the service to use the host path for the run directory
