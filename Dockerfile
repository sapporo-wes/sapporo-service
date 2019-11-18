FROM python:slim

WORKDIR /opt/SAPPORO/SAPPORO-service

RUN apt update && \
    apt install -y \
    build-essential \
    curl \
    iproute2 \
    jq \
    procps \
    tree

COPY etc/requirements.txt /tmp

RUN pip install -U pip wheel setuptools && \
    pip install -r /tmp/requirements.txt && \
    rm -rf /tmp/requirements.txt

# The workflow engine you want to use.
# RUN apt install -y \
#     cwltool && \
#     apt clean && \
#     rm -rf /var/lib/apt/lists/*

COPY src /opt/SAPPORO/SAPPORO-service/src
COPY service-info.yml /opt/SAPPORO/SAPPORO-service
COPY workflow-info.yml /opt/SAPPORO/SAPPORO-service

CMD ["/usr/local/bin/python3", "/opt/SAPPORO/SAPPORO-service/src/run.py"]
