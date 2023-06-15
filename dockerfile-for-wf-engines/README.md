# Dockerfile for Workflow Engines

## Why?

When using the official docker image such as `broadinstitute/cromwell:85`,

```
docker: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.32' not found (required by docker)
```

an error like the above appears.

In Sapporo, within `run.sh`,

```bash
local container="broadinstitute/cromwell:85"
docker run --rm ${D_SOCK} -v ${run_dir}:${run_dir} -v /tmp:/tmp -v /usr/bin/docker:/usr/bin/docker -w=${exe_dir} ${container} run ${wf_engine_params} ${wf_url} -i ${wf_params} -m ${exe_dir}/metadata.json
```

We mount the docker command and docker socket on the host side and use them, but because the glibc version required by Docker on the host side and the glibc provided by the container image are different, an error like the one above occurs.

Therefore, we create, provide, and use an workflow engine image with docker-ce installed, using the official image of the workflow engine as the base.

## Cromwell

To build and push:

```bash
$ docker build -f ./Dockerfile-cromwell -t ghcr.io/sapporo-wes/cromwell-with-docker:80 .
$ docker push ghcr.io/sapporo-wes/cromwell-with-docker:80
```
