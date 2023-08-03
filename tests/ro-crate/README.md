# Tests for the RO-Crate Feature

This directory hosts a series of tests for [`../../sapporo/ro-crate.py`](../../sapporo/ro-crate.py). Sapporo executes `ro-crate.py` within `run.sh` after a workflow run, generating a `ro-crate-metadata.json` file in each run_dir, using the [RO-Crate](https://www.researchobject.org/ro-crate/).

The function used for execution within `run.sh` is:

```bash
function generate_ro_crate() {
  python3 -c "from sapporo.ro_crate import generate_ro_crate; generate_ro_crate('${run_dir}')" || echo "{}" >"${run_dir}/ro-crate-metadata.json" || true
}
```

The purpose of the tests in this directory is to confirm the generation of RO-Crates following the execution of workflows using various workflow engines. Additionally, examples of the generated RO-Crates are provided.

## Running the Tests

The tests execute various workflows found in the `../curl_example/post_runs` directory, followed by the verification of the RO-Crates generated within each directory.

To run these tests, follow the commands below:

```bash
# Preparations, launch Sapporo (Execute from the library root directory)
$ cd ../../
$ docker compose -f docker-compose.dev.yml up -d
$ docker compose -f docker-compose.dev.yml exec app sapporo

# Run the tests
$ cd tests/ro-crate
$ bash run_ro-crate_test.sh
```

## How to Generate [`./ro-crate-metadata.json`](./ro-crate-metadata.json)

The [`./ro-crate-metadata.json`](./ro-crate-metadata.json) is a small example of RO-Crate generated by Sapporo.
It is generated using [Yevis-cli](https://github.com/sapporo-wes/yevis-cli), which is utilized as a client for sending run requests to Sapporo.

```bash
# Start Sapporo-service on localhost:1122

$ ./yevis --version
yevis 0.5.8
$ yevis test --wes-location http://localhost:1122 --fetch-ro-crate \
  https://raw.githubusercontent.com/sapporo-wes/yevis-cli/main/tests/test-metadata-CWL-apache2.yml
Start yevis
Running validate
Validating https://raw.githubusercontent.com/sapporo-wes/yevis-cli/main/tests/test-metadata-CWL-apache2.yml
Success validate
Running test
Use WES location: http://localhost:1122/ for testing
Test workflow_id: c13b6e27-a4ee-426f-8bdb-8cf5c4310bad, version: 1.0.0
Testing test case: test_1
WES run_id: 27469c13-2f6d-47af-9623-39cdee5f1a04
Complete test case: test_1
Passed all test cases in workflow_id: c13b6e27-a4ee-426f-8bdb-8cf5c4310bad, version: 1.0.0
Success test
sapporo-service is not running. So skip stopping it.
$ ls test-logs/
ro-crate-metadata_c13b6e27-a4ee-426f-8bdb-8cf5c4310bad_1.0.0_test_1.json
$ cp test-logs/ro-crate-metadata_c13b6e27-a4ee-426f-8bdb-8cf5c4310bad_1.0.0_test_1.json ./ro-crate-metadata.json
```

In addition, copy the complete run directory from which the `ro-crate-metadata.json` was generated to the `ro-crate_dir` directory.

```bash
$ cp -r ../../run/27/27469c13-2f6d-47af-9623-39cdee5f1a04 ./ro-crate_dir
```