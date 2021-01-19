# Tests

## Unit test

Run inside a container.

```bash
$ pytest ./unit_test

# Show logs
$ pytest -s ./unit_test
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

## Server startup test
