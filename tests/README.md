# Tests

## Unit test

Run inside a container.

```bash
$ pytest ./unit_test

# Show logs
$ pytest -s ./unit_test

# Select TEST SERVER as uwsgi or flask (default: uwsgi)
$ TEST_SERVER_MODE=uwsgi pytest ./unit_test
$ TEST_SERVER_MODE=flask pytest ./unit_test
```

## Lint and style check

Run inside a container.

```bash
$ bash ./lint_and_style_check/flake8.sh
$ bash ./lint_and_style_check/isort.sh
$ bash ./lint_and_style_check/mypy.sh

or

$ bash ./lint_and_style_check/run_all.sh
```

## curl examples

`./curl` contains an example of using curl to send a request.
