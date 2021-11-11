# FROM python:3.8.12-buster
FROM python@sha256:48ad1f497c43eb06c95f4177c705631c7dd600791987b421f9fed464757687e2 as builder

WORKDIR /app
COPY . .
RUN python3 -m pip install --no-cache-dir --progress-bar off -U pip setuptools wheel && \
    python3 -m pip install --no-cache-dir --progress-bar off .

# FROM python:3.8.12-slim-buster
FROM python@sha256:687563144f2de27d7820d6b04103ffeab8afb7245df5dfeedce67d2150b630bf

LABEL org.opencontainers.image.authors="DDBJ(DNA Data Bank of Japan) <t.ohta@nig.ac.jp>"
LABEL org.opencontainers.image.url="https://github.com/sapporo-wes/sapporo-service"
LABEL org.opencontainers.image.source="https://github.com/sapporo-wes/sapporo-service/blob/main/Dockerfile"
LABEL org.opencontainers.image.version="1.0.19"
LABEL org.opencontainers.image.description="sapporo-service is a standard implementation conforming to the \
    Global Alliance for Genomics and Health (GA4GH) Workflow Execution Service (WES) API specification."
LABEL org.opencontainers.image.licenses="Apache2.0"

ADD https://download.docker.com/linux/static/stable/x86_64/docker-20.10.8.tgz /tmp/
RUN tar xf /tmp/docker-20.10.8.tgz -C /tmp && \
    mv /tmp/docker/* /usr/bin/ && \
    rmdir /tmp/docker && \
    rm -f /tmp/docker-20.10.8.tgz

RUN apt update && \
    apt install -y --no-install-recommends \
    curl \
    jq \
    libxml2 \
    tini && \
    apt clean &&\
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages
COPY --from=builder /usr/local/bin/uwsgi /usr/local/bin/uwsgi
COPY --from=builder /usr/local/bin/sapporo /usr/local/bin/sapporo

WORKDIR /app
COPY . .

ENV SAPPORO_HOST 0.0.0.0
ENV SAPPORO_PORT 1122
ENV SAPPORO_DEBUG False

EXPOSE 1122

ENTRYPOINT ["tini", "--"]
CMD ["uwsgi", "--yaml", "/app/uwsgi.yml", "--http", "0.0.0.0:1122"]
