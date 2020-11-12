FROM python:3.8.2-slim-buster

RUN apt update && \
    apt install -y --no-install-recommends \
                build-essential \
                curl \
                apt-transport-https \
                ca-certificates \
                gnupg-agent gnupg \
                software-properties-common \
                jq \
                git && \
    (curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -) && \
    add-apt-repository \
        "deb [arch=amd64] https://download.docker.com/linux/debian \
        $(lsb_release -cs) \
        stable" && \
    apt-get update && \
    apt-get install -y docker-ce-cli && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 install -U pip setuptools wheel
