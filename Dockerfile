FROM python:3.8.2-slim-buster

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

RUN pip install -U pip setuptools wheel && \
    pip install -r requirements.txt

COPY . .

RUN python3 setup.py install

ENV SAPPORO_HOST 0.0.0.0
ENV SAPPORO_PORT 8080
ENV SAPPORO_DEBUG False

EXPOSE 8080

ENTRYPOINT ["tini", "--"]
CMD ["sapporo"]
