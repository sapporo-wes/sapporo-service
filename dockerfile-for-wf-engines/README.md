# Dockerfile for Workflow Engines

## Why?

When using the official docker image such as `broadinstitute/cromwell:87`,

```bash
docker: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.32' not found (required by docker)
```

an error like the above appears.

In Sapporo, within `run.sh`,

```bash
local container="broadinstitute/cromwell:85"
docker run --rm ${D_SOCK} -v ${run_dir}:${run_dir} -v /tmp:/tmp -v /usr/bin/docker:/usr/bin/docker -w=${exe_dir} ${container} run ${wf_engine_params} ${wf_url} -i ${wf_params} -m ${exe_dir}/metadata.json
```

We mount the Docker command and Docker socket from the host and use them inside the container. However, due to the difference in glibc versions, an error occurs.

To solve this issue, we create and use a custom workflow engine image with Docker CE installed, using the official image of the workflow engine as the base.

## Cromwell

To build and push:

```bash
docker build -f ./Dockerfile-cromwell -t ghcr.io/sapporo-wes/cromwell-with-docker:87 .
docker push ghcr.io/sapporo-wes/cromwell-with-docker:87
```
