# Testing

## Test Resources

[./resources](./resources) contains various files used for testing, such as workflow files and input files.
These file sets are utilized in the tests described below.

## Unit Tests

Unit tests are designed to verify the functionality of the Sapporo library and API requests.
They also include tests for command-line interface (CLI) arguments and mode switching using environment variables.

Tests are written using `pytest` and can be executed either on the host or inside a Docker container.

```bash
# Install dependencies (run at the root directory of the Sapporo library)
$ python3 -m pip install .[tests]

$ pytest ./tests/unit_test

# To view the logs
$ pytest -s ./tests/unit_test
```

## Linting and Style Checks

inting and style checks are performed using `flake8`, `isort`, and `mypy`.

```bash
$ bash ./tests/lint_and_style_check/flake8.sh
$ bash ./tests/lint_and_style_check/isort.sh
$ bash ./tests/lint_and_style_check/mypy.sh

# Run all checks at once
$ bash ./tests/lint_and_style_check/run_all.sh
```

## Curl Examples

The [./curl_example](./curl_example) directory contains examples of using `curl`` to send workflow execution requests to the WES API.

For instance, to execute post_runs with cwltool, follow the example below:

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
$ bash ./tests/curl_example/cwltool_attach_all_files.sh
$ bash ./tests/curl_example/cwltool_attach_all_files.sh
POST /runs is succeeded:
{
  "run_id": "72516758-ea36-4e9d-b74c-8af5e28b19bd"
}

Please access to the following URL to get the run status:

curl -fsSL -X GET http://127.0.0.1:1122/runs/72516758-ea36-4e9d-b74c-8af5e28b19bd

# Then
$ curl -fsSL -X GET http://127.0.0.1:1122/runs/72516758-ea36-4e9d-b74c-8af5e28b19bd
```

## RO-Crate

Please refer to the [README.md](./ro-crate/README.md) in the [./ro-crate](./ro-crate) directory for details.
