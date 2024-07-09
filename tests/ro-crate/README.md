# Tests for the RO-Crate Feature

This directory contains a suite of tests designed to validate the functionality of the [`../../sapporo/ro-crate.py`](../../sapporo/ro-crate.py) script with in the Sapporo project. The script is executed by `run.sh` after each workflow run to generate a `ro-crate-metadata.json` file in the corresponding run directory, leveraging the [RO-Crate standard](https://www.researchobject.org/ro-crate/).

The generate_ro_crate function in `run.sh` triggers the execution of ro-crate.py as shown below:

```bash
function generate_ro_crate() {
  python3 -c "from sapporo.ro_crate import generate_ro_crate; generate_ro_crate('${run_dir}')" || echo "{}" >${ro_crate}
}
```

The tests aim to verify that RO-Crate metadata files are correctly generated across different workflow engines. This directory also provides example RO-Crates for reference.

## Running the Tests

To execute the tests, various workflows located in the [../curl_example](../curl_example) directory are run, followed by verification of the generated RO-Crates.

Run the following commands to initiate the tests:

```bash
# Setup and start Sapporo (Execute from the root directory of the library)
$ cd ../../
$ docker compose -f compose.dev.yml up -d
$ docker compose -f compose.dev.yml exec app sapporo

# Run the RO-Crate tests
$ cd tests/ro-crate
$ bash run_ro-crate_test.sh
```

## Generating a Sample [`./ro-crate-metadata.json`](./ro-crate-metadata.json)

The provided [`./ro-crate-metadata.json`](./ro-crate-metadata.json) serves as a small example of an RO-Crate generated by Sapporo. The following steps demonstrate how to generate this sample:

```bash
# Initialize Sapporo service on localhost:1122

$ bash ../curl_example/cwltool_fetch_remote_resource.sh
POST /runs is succeeded:
{"run_id":"b5fbc050-ebad-49d7-97c0-a633f1dfe8bd"}

Please access to the following URL to get the run status:

curl -fsSL -X GET http://127.0.0.1:1122/runs/b5fbc050-ebad-49d7-97c0-a633f1dfe8bd
$ curl -fsSL -X GET http://127.0.0.1:1122/runs/b5fbc050-ebad-49d7-97c0-a633f1dfe8bd | jq .state
"COMPLETE"
$ curl -s http://127.0.0.1:1122/runs/b5fbc050-ebad-49d7-97c0-a633f1dfe8bd/ro-crate > ./ro-crate-metadata.json
```

You can also copy the complete run directory to the ro-crate_dir for further inspection:

```bash
curl -s http://127.0.0.1:1122/runs/b5fbc050-ebad-49d7-97c0-a633f1dfe8bd/ro-crate?download=true -o ro-crate.zip
unzip ro-crate.zip -d ./temp_unzip_dir
mv ./temp_unzip_dir/sapporo_b5fbc050-ebad-49d7-97c0-a633f1dfe8bd_ro_crate ./ro-crate_dir
rm -rf ./temp_unzip_dir
```

### License Considerations

According to the Crate section of [Workflow-RO-Crate](https://about.workflowhub.eu/Workflow-RO-Crate/), "The Crate MUST specify a license. The license is assumed to apply to any content of the crate, unless overridden by a license on individual File entities." While Sapporo aims to add a license during the Workflow-Run-Crate creation, it currently lacks a feature for specifying a license at the time of workflow execution due to WES limitations. For now, the license property is added manually as a quick fix.