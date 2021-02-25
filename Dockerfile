FROM python:3.8.7-slim-buster

RUN apt update && \
    apt install -y --no-install-recommends \
    build-essential \
    curl \
    jq \
    tini && \
    apt clean &&\
    rm -rf /var/lib/apt/lists/*

ENV DOCKER_BINARY_VERSION "20.10.3"
ENV DOCKER_BINARY_TAR "docker-${DOCKER_BINARY_VERSION}.tgz"
ENV DOCKER_BINARY_PATH "https://download.docker.com/linux/static/stable/x86_64/${DOCKER_BINARY_TAR}"

ADD ${DOCKER_BINARY_PATH} /
RUN tar xf "/${DOCKER_BINARY_TAR}" && mv /docker/* /usr/bin/ && \
    rmdir /docker && rm -f ${DOCKER_BINARY_PATH}

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --progress-bar off -U pip setuptools wheel && \
    pip install --no-cache-dir --progress-bar off -r requirements.txt

COPY . .

RUN pip install --no-cache-dir --progress-bar off -e .

ENV SAPPORO_HOST 0.0.0.0
ENV SAPPORO_PORT 1122

EXPOSE 1122

ENTRYPOINT ["tini", "--"]
CMD ["sapporo"]
