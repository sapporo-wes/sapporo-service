# Tests

## Resources

This directory stores various files, such as workflow files and input files for testing.

The directory structure is as follows:

```bash
$ tree resources/
resources/
├── cromwell
│   └── dockstore-tool-bamstats
│       ├── Dockstore.cwl
│       ├── Dockstore.wdl
│       ├── test.json
│       ├── test.wdl.json
│       └── tiny.bam
├── cwltool
│   ├── ERR034597_1.small.fq.gz
│   ├── ERR034597_2.small.fq.gz
│   ├── fastqc.cwl
│   ├── trimming_and_qc.cwl
│   ├── trimming_and_qc_packed.cwl
│   ├── trimming_and_qc_remote.cwl
│   └── trimmomatic_pe.cwl
├── nextflow
│   ├── file_input.nf
│   ├── nf_test_input.txt
│   ├── params_outdir.nf
│   └── str_input.nf
└── snakemake
    ├── data
    │   ├── genome.fa
    │   ├── genome.fa.amb
    │   ├── genome.fa.ann
    │   ├── genome.fa.bwt
    │   ├── genome.fa.fai
    │   ├── genome.fa.pac
    │   ├── genome.fa.sa
    │   └── samples
    │       ├── A.fastq
    │       ├── B.fastq
    │       └── C.fastq
    ├── envs
    │   ├── calling.yaml
    │   ├── mapping.yaml
    │   └── stats.yaml
    ├── scripts
    │   └── plot-quals.py
    └── Snakefile

9 directories, 31 files
```

These sets of files are used in the following tests.

## Unit Tests

These tests focus on the functions of the Sapporo library and API requests. It also includes tests for arguments as a command-line interface (CLI) and mode switching using environment values.

Tests are written using `pytest` and can be executed either on the host or inside a Docker container.

```bash
# Installing dependencies (run at the root directory of the Sapporo library)
$ python3 -m pip install .[tests]

$ pytest ./tests/unit_test

# If you want to see the logs
$ pytest -s ./tests/unit_test

# Specify uwsgi or flask with TEST_SERVER_MODE (default: uwsgi)
$ TEST_SERVER_MODE=uwsgi pytest ./tests/unit_test
$ TEST_SERVER_MODE=flask pytest ./tests/unit_test
```

## Linting and Style Checks

inting and style checks are performed using `flake8`, `isort`, and `mypy`.

```bash
$ bash ./tests/lint_and_style_check/flake8.sh
$ bash ./tests/lint_and_style_check/isort.sh
$ bash ./tests/lint_and_style_check/mypy.sh

# Run all at once
$ bash ./tests/lint_and_style_check/run_all.sh
```

## Curl Example

This directory stores examples of executing each WES API request with curl. **In particular, `./curl_example/post_runs` provides examples for each workflow engine and should be very useful for reference.**

```bash
$ tree ./curl_example/post_runs
./curl_example/post_runs
├── cromwell
│   ├── bamstats_cwl
│   │   ├── post_runs.sh
│   │   └── tags.json
│   └── bamstats_wdl
│       ├── post_runs.sh
│       └── tags.json
├── cwltool
│   ├── attach_all_files
│   │   ├── post_runs.sh
│   │   └── workflow_params.json
│   ├── registered_workflow
│   │   ├── post_runs.sh
│   │   └── workflow_params.json
│   ├── remote_workflow
│   │   ├── post_runs.sh
│   │   └── workflow_params.json
│   ├── tags_workflow_name
│   │   ├── post_runs.sh
│   │   ├── tags.json
│   │   └── workflow_params.json
│   └── workflow_engine_parameters
│       ├── post_runs.sh
│       ├── workflow_engine_parameters.json
│       └── workflow_params.json
├── nextflow
│   ├── file_input
│   │   ├── post_runs.sh
│   │   └── workflow_params.json
│   ├── file_input_with_docker
│   │   ├── post_runs.sh
│   │   ├── workflow_engine_parameters.json
│   │   └── workflow_params.json
│   ├── params_outdir
│   │   ├── post_runs.sh
│   │   └── workflow_params.json
│   ├── params_outdir_with_docker
│   │   ├── post_runs.sh
│   │   ├── workflow_engine_parameters.json
│   │   └── workflow_params.json
│   ├── str_input
│   │   ├── post_runs.sh
│   │   └── workflow_params.json
│   └── str_input_with_docker
│       ├── post_runs.sh
│       ├── workflow_engine_parameters.json
│       └── workflow_params.json
├── post_runs.sh
└── snakemake
    ├── tutorial_wf
    │   ├── post_runs.sh
    │   └── workflow_engine_parameters.json
    └── tutorial_wf_remote
        ├── post_runs.sh
        └── workflow_engine_parameters.json

19 directories, 36 files
```

For instance, to execute post_runs with cwltool, you can follow the example below:

```bash
# Start the container for sapporo-dev
$ docker compose -f compose.dev.yml up -d

# Start Sapporo
$ docker compose -f compose.dev.yml exec app sapporo
...
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:1122
 * Running on http://172.24.0.2:1122
Press CTRL+C to quit

# Execute the post_runs script
$ SAPPORO_HOST=0.0.0.0 SAPPORO_PORT=1122 bash ./tests/curl_examples/post_runs/cwltool/attach_all_files/post_runs.sh
{
  "run_id": "0b0a0b0a-0b0a-0b0a-0b0a-0b0a0b0a0b0a"
}

# Additionally, since `${PWD}/runs` is set as run_dir, you can check the actual run files
$ ls ./runs/0b/0a/0b0a0b0a-0b0a-0b0a-0b0a-0b0a0b0a0b0a
```

## RO-Crate

Please refer to the [README.md](./ro-crate/README.md) in the `./ro-crate` directory for details.
