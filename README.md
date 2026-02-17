# sapporo-service

[![DOI](https://zenodo.org/badge/220937589.svg)](https://zenodo.org/badge/latestdoi/220937589)
[![Apache License](https://img.shields.io/badge/license-Apache%202.0-orange.svg?style=flat&color=important)](http://www.apache.org/licenses/LICENSE-2.0)
[![Docs](https://img.shields.io/badge/docs-online-blue)](https://sapporo-wes.github.io/sapporo-service/)

<p align="center">
  <img src="https://raw.githubusercontent.com/sapporo-wes/sapporo/main/logo/sapporo-service.svg" width="400" alt="sapporo-service logo">
</p>

The sapporo-service is a standard implementation of the [Global Alliance for Genomics and Health](https://www.ga4gh.org) (GA4GH) [Workflow Execution Service](https://github.com/ga4gh/workflow-execution-service-schemas) (WES) API specification. WES provides a standardized way to submit, monitor, and retrieve results from computational workflows across different platforms.

The service builds on GA4GH WES 1.1.0 with additional capabilities defined in the [sapporo-wes-2.0.0 specification](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/sapporo-wes/sapporo-service/main/sapporo-wes-spec-2.0.0.yml), including output file downloads, [RO-Crate](https://www.researchobject.org/ro-crate/) metadata generation, run deletion, and JWT authentication. Each workflow engine runs inside its own Docker container, so the service does not require any engine-specific installation.

## Supported Workflow Engines

- [cwltool](https://github.com/common-workflow-language/cwltool)
- [nextflow](https://www.nextflow.io)
- [Toil (experimental)](https://toil.ucsc-cgl.org)
- [cromwell](https://github.com/broadinstitute/cromwell)
- [snakemake](https://snakemake.readthedocs.io/en/stable/)
- [ep3 (experimental)](https://github.com/tom-tan/ep3)
- [StreamFlow (experimental)](https://github.com/alpha-unito/streamflow)

## Quick Start

```bash
docker compose up -d
curl localhost:1122/service-info
```

See the [Getting Started](docs/getting-started.md) guide for a complete walkthrough including workflow submission.

## Documentation

Full documentation is available at **<https://sapporo-wes.github.io/sapporo-service/>**.

- [Getting Started](docs/getting-started.md) - First-time tutorial: start the service, submit a workflow, retrieve results
- [Installation](docs/installation.md) - Install with pip or Docker, volume mount configuration
- [Configuration](docs/configuration.md) - CLI options, environment variables, executable workflows
- [Authentication](docs/authentication.md) - JWT authentication, sapporo/external mode
- [Architecture](docs/architecture.md) - run.sh abstraction, run directory, SQLite, RO-Crate, code structure
- [RO-Crate](docs/ro-crate.md) - RO-Crate metadata generation specification
- [Development](docs/development.md) - Development environment, testing, release process

## License

This project is licensed under the [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) license. See the [LICENSE](./LICENSE) file for details.
