# FROM python:3.8.8-buster
FROM python@sha256:d90d328f14fc16e1b2be053ca18a01bb561c543730d5d781b58cc561faabac33 as builder

WORKDIR /app
COPY . .
RUN python3 -m pip install --no-cache-dir --progress-bar off -U pip setuptools wheel && \
    python3 -m pip install --no-cache-dir --progress-bar off .

# FROM python:3.8.8-slim-buster
FROM python@sha256:1389669225e7fa05a9bac20d64551b6b6d84ee3200330d8d8de74c6d2314fdc7

LABEL org.opencontainers.image.authors="DDBJ(DNA Data Bank of Japan) <t.ohta@nig.ac.jp>"
LABEL org.opencontainers.image.url="https://github.com/ddbj/SAPPORO-service"
LABEL org.opencontainers.image.source="https://github.com/ddbj/SAPPORO-service/blob/master/Dockerfile"
LABEL org.opencontainers.image.version="1.0.12"
LABEL org.opencontainers.image.description="SAPPORO-service is a standard implementation conforming to the \
    Global Alliance for Genomics and Health (GA4GH) Workflow Execution Service (WES) API specification."
LABEL org.opencontainers.image.licenses="Apache2.0"

ADD https://download.docker.com/linux/static/stable/x86_64/docker-20.10.3.tgz /tmp/
RUN tar xf /tmp/docker-20.10.3.tgz -C /tmp && \
    mv /tmp/docker/* /usr/bin/ && \
    rmdir /tmp/docker && \
    rm -f /tmp/docker-20.10.3.tgz

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
