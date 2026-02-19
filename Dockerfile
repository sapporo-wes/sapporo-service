FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ARG TARGETARCH
ARG VERSION=dev

LABEL org.opencontainers.image.authors="Bioinformatics and DDBJ Center <tazro.ohta@chiba-u.jp>"
LABEL org.opencontainers.image.url="https://github.com/sapporo-wes/sapporo-service"
LABEL org.opencontainers.image.source="https://github.com/sapporo-wes/sapporo-service/blob/main/Dockerfile"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.description="The sapporo-service is a standard implementation conforming to the Global Alliance for Genomics and Health (GA4GH) Workflow Execution Service (WES) API specification."
LABEL org.opencontainers.image.licenses="Apache2.0"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    jq \
    libmagic1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Docker CLI (multi-architecture)
RUN DOCKER_ARCH=$(case "${TARGETARCH}" in \
    amd64) echo "x86_64" ;; \
    arm64) echo "aarch64" ;; \
    *) echo "x86_64" ;; \
    esac) && \
    curl -fsSL -o /tmp/docker.tgz "https://download.docker.com/linux/static/stable/${DOCKER_ARCH}/docker-29.2.1.tgz" && \
    tar -xzf /tmp/docker.tgz -C /tmp && \
    mv /tmp/docker/docker /usr/local/bin/docker && \
    rm -rf /tmp/docker /tmp/docker.tgz

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

# Named volume inherits image permissions on first creation;
# make writable so arbitrary UID (dev) can run uv commands.
RUN uv sync --frozen --all-extras && \
    chmod -R a+rwX .venv

COPY . .

# Writable home for arbitrary UID (dev containers use user: UID:GID).
ENV HOME=/home/app
RUN mkdir -p /home/app && chmod 777 /home/app

ENV PATH="/app/.venv/bin:${PATH}"

ENTRYPOINT []
CMD ["sapporo"]
