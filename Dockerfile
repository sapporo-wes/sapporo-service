FROM python:3.12-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

LABEL org.opencontainers.image.authors="Bioinformatics and DDBJ Center <tazro.ohta@chiba-u.jp>"
LABEL org.opencontainers.image.url="https://github.com/sapporo-wes/sapporo-service"
LABEL org.opencontainers.image.source="https://github.com/sapporo-wes/sapporo-service/blob/main/Dockerfile"
LABEL org.opencontainers.image.version="2.1.0"
LABEL org.opencontainers.image.description="The sapporo-service is a standard implementation conforming to the Global Alliance for Genomics and Health (GA4GH) Workflow Execution Service (WES) API specification."
LABEL org.opencontainers.image.licenses="Apache2.0"

RUN apt update && \
    apt install -y --no-install-recommends \
    curl \
    jq && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /tmp
RUN curl -Lo docker.tgz https://download.docker.com/linux/static/stable/x86_64/docker-26.1.4.tgz && \
    tar -xzf docker.tgz && \
    mv docker/docker /usr/local/bin/docker && \
    rm -rf docker docker.tgz

WORKDIR /app
COPY . .
RUN uv pip install --system --no-cache .

EXPOSE 1122

ENTRYPOINT []
CMD ["sapporo"]
