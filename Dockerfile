# Stages:
#   base:    OS packages, the Docker CLI and the runtime environment shared by the other stages
#   dev:     the development image built by compose.dev.yml, with the tests extra and the dev group
#   build:   installs sapporo and its runtime dependencies into /app/.venv
#   release: the published image (the default target); /app/.venv on top of base, without uv

# The Docker CLI is a static binary, so it runs on the Debian base below
FROM docker:29-cli AS docker-cli

FROM python:3.14-slim-trixie AS base

ARG VERSION=0.0.0.dev0

LABEL org.opencontainers.image.authors="Bioinformatics and DDBJ Center <tazro.ohta@chiba-u.jp>"
LABEL org.opencontainers.image.url="https://github.com/sapporo-wes/sapporo-service"
LABEL org.opencontainers.image.source="https://github.com/sapporo-wes/sapporo-service/blob/main/Dockerfile"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.description="The sapporo-service is a standard implementation conforming to the Global Alliance for Genomics and Health (GA4GH) Workflow Execution Service (WES) API specification."
LABEL org.opencontainers.image.licenses="Apache2.0"

# Debian can publish security updates between the rebuilds of the base image tag
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    jq \
    libmagic1t64 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# sapporo runs from /app/.venv, which uv creates without pip, so the pip of the base image is not used
RUN python -m pip uninstall -y --root-user-action=ignore pip

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /app

# Writable home for arbitrary UID (dev containers use user: UID:GID).
ENV HOME=/home/app
RUN mkdir -p /home/app && chmod 777 /home/app

ENV PATH="/app/.venv/bin:${PATH}"

ENTRYPOINT []
CMD ["sapporo"]

FROM base AS dev

ARG VERSION=0.0.0.dev0

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
RUN mkdir -p sapporo

# Named volume inherits image permissions on first creation;
# make writable so arbitrary UID (dev) can run uv commands.
RUN uv sync --frozen --all-extras --no-install-project && \
    chmod -R a+rwX .venv

COPY . .

# Install the project with version injected from the build arg.
RUN SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION} uv sync --frozen --all-extras

FROM base AS build

ARG VERSION=0.0.0.dev0

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/

# Only /app/.venv leaves this stage, so the cache of uv and the source tree stay out of the release image
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY sapporo ./sapporo
RUN SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION} uv sync --frozen --no-dev --no-editable

FROM base AS release

COPY --from=build /app/.venv /app/.venv
