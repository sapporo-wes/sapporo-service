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

[./curl_example](./curl_example) contains examples of executing each WES API request with curl.
**Notably, [./curl_example/post_runs](./curl_example/post_runs) provides examples for each workflow engine and serves as a valuable reference.**

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
$ SAPPORO_HOST=0.0.0.0 SAPPORO_PORT=1122 bash ./tests/curl_examples/post_runs/cwltool/attach_all_files/post_runs.sh
{
  "run_id": "0b0a0b0a-0b0a-0b0a-0b0a-0b0a0b0a0b0a"
}

# Additionally, since `${PWD}/runs` is set as run_dir, you can check the actual run files
$ ls ./runs/0b/0a/0b0a0b0a-0b0a-0b0a-0b0a-0b0a0b0a0b0a
```

## RO-Crate

Please refer to the [README.md](./ro-crate/README.md) in the [./ro-crate](./ro-crate) directory for details.
