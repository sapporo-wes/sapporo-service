FROM python:3.8.7-slim-buster

RUN apt update && \
    apt install -y --no-install-recommends \
    build-essential \
    curl \
    jq \
    tini && \
    apt clean &&\
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --progress-bar off -U pip setuptools wheel && \
    pip install --no-cache-dir --progress-bar off -r requirements.txt

COPY . .

RUN pip install --no-cache-dir --progress-bar off -e .

ENV SAPPORO_HOST 0.0.0.0
ENV SAPPORO_PORT 8080

EXPOSE 8080

ENTRYPOINT ["tini", "--"]
CMD ["sapporo"]
