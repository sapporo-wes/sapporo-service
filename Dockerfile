FROM python:3.7.5-slim-buster

RUN apt update && \
    apt install -y \
    awscli \
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

CMD ["tail", "-f", "/dev/null"]
