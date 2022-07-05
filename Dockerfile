FROM python:3.8.13-buster as builder

WORKDIR /app
COPY . .
RUN python3 -m pip install --no-cache-dir --progress-bar off -U pip setuptools wheel && \
    python3 -m pip install --no-cache-dir --progress-bar off .

FROM python:3.8.13-slim-buster

LABEL org.opencontainers.image.authors="Bioinformatics and DDBJ Center <t.ohta@nig.ac.jp>"
LABEL org.opencontainers.image.url="https://github.com/sapporo-wes/sapporo-service"
LABEL org.opencontainers.image.source="https://github.com/sapporo-wes/sapporo-service/blob/main/Dockerfile"
LABEL org.opencontainers.image.version="1.3.1"
LABEL org.opencontainers.image.description="sapporo-service is a standard implementation conforming to the \
    Global Alliance for Genomics and Health (GA4GH) Workflow Execution Service (WES) API specification."
LABEL org.opencontainers.image.licenses="Apache2.0"

RUN apt update && \
    apt install -y --no-install-recommends \
    curl \
    jq \
    libxml2 \
    tini && \
    apt clean &&\
    rm -rf /var/lib/apt/lists/*

WORKDIR /tmp
RUN curl -O https://download.docker.com/linux/static/stable/$(uname -m)/docker-20.10.9.tgz && \
    tar -xzf docker-20.10.9.tgz && \
    mv docker/* /usr/bin/ && \
    rm -rf docker docker-20.10.9.tgz

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
