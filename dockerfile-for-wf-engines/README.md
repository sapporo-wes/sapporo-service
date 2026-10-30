# Dockerfile for Workflow Engines

## Why?

Sapporo runs workflow engines inside Docker containers via DinD (Docker-in-Docker), mounting the host Docker socket (`/var/run/docker.sock`) into the engine container.
Cromwell starts a container for each WDL task with `runtime { docker: "..." }`, so its image must have the Docker CLI.
The official `broadinstitute/cromwell` image does not include the Docker CLI, and it keeps the OS packages of its release date.

## Cromwell

`Dockerfile-cromwell` adds the jar of a Cromwell release and the Docker CLI to the `eclipse-temurin` JRE image.
Docker Hub rebuilds the base image tags (`eclipse-temurin:17-jre-resolute` and `docker:29-cli`) with security updates, so always build with `--pull`.
The image tag is the Cromwell version.
To include the newest base images, build the image again and push it with the same tag.

Build and push:

```bash
docker build --pull -f ./Dockerfile-cromwell -t ghcr.io/sapporo-wes/cromwell-with-docker:92 .
docker push ghcr.io/sapporo-wes/cromwell-with-docker:92
```

If a host already has the image, `run.sh` does not pull it again.
After you push the image with the same tag, run `docker pull ghcr.io/sapporo-wes/cromwell-with-docker:92` on each host.

To upgrade Cromwell, read the release notes first.
Then update the release URL and the checksum in `Dockerfile-cromwell`, the tag in the commands above, and the tag in `sapporo/run.sh` (`run_cromwell()` function).
GitHub shows the checksum of each release file:

```bash
gh api repos/broadinstitute/cromwell/releases/tags/<version> --jq '.assets[] | select(.name == "cromwell-<version>.jar") | .digest'
```

If the release notes require a different Java version, change the version in the `eclipse-temurin` tag.
