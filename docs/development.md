# Development

## Development Environment

### Docker (Recommended)

Start the development environment with bind-mounted source code:

```bash
docker compose -f compose.dev.yml up -d --build
docker compose -f compose.dev.yml exec app bash
```

The development compose file:

- Builds from the local Dockerfile
- Mounts the source tree at `/app`
- Uses a named volume for `.venv` (avoids host/container venv conflicts)
- Runs `sleep infinity` so you can exec into the container and start the service manually

Inside the container, start the server in debug mode:

```bash
sapporo --debug
```

### Local Setup

Install the package with test dependencies:

```bash
uv sync --all-extras
```

## Running the Server

Start the service in debug mode for development:

```bash
sapporo --debug
```

The `--debug` flag enables hot-reloading and verbose logging. Access `http://localhost:1122/docs` for the interactive Swagger UI.

## Testing

### Running Tests

```bash
# Run all tests
uv run pytest

# Verbose output
uv run pytest -v

# Specific file
uv run pytest tests/unit/test_utils.py

# Specific test
uv run pytest tests/unit/test_utils.py::test_now_str_returns_rfc3339_utc_format

# Run in random order (check for order dependencies)
uv run pytest -p randomly -v

# Exclude slow tests
uv run pytest -m "not slow"
```

### Mutation Testing

```bash
# Run according to [tool.mutmut] settings in pyproject.toml
uv run mutmut run

# View results
uv run mutmut results

# Show details of a survived mutant
uv run mutmut show <mutant_id>
```

#### Known Limitations

mutmut v3 copies source files to a `mutants/` directory and applies mutations there. Modules like `sapporo/auth.py` that resolve data files via `Path(__file__)` fail because the data files do not exist at the copy destination. Currently `sapporo/utils.py`, `sapporo/exceptions.py`, and `sapporo/config.py` are targeted.

### Adding Tests

1. Add tests to the `test_<module>.py` file corresponding to the target module
2. Naming convention: `test_<target>_<condition>_<expected_result>()`
3. Use hypothesis `@given` when property-based testing is applicable
4. Confirm PASS with `uv run pytest -v`
5. Confirm lint-clean with `uv run ruff check tests/` and `uv run ruff format --check tests/`
6. Optionally verify detection power with `uv run mutmut run --paths-to-mutate sapporo/<module>.py`

## Linting and Type Checking

The project uses [ruff](https://docs.astral.sh/ruff/) for linting/formatting and [mypy](https://mypy-lang.org/) for type checking. Configuration is in `pyproject.toml`.

```bash
# Lint
uv run ruff check .

# Format check
uv run ruff format --check .

# Auto-fix lint issues
uv run ruff check --fix .

# Auto-format
uv run ruff format .

# Type check
uv run mypy
```

## OpenAPI Spec Generation

The OpenAPI specification file (`openapi/sapporo-wes-spec-X.X.X.yml`) is generated from the FastAPI application. Regenerate it after changing schemas, endpoint descriptions, or the spec version:

```bash
uv run python -m sapporo.config
```

The generated file should be committed to the repository.

### Spec Version

`SAPPORO_WES_SPEC_VERSION` in `sapporo/config.py` is the single source of truth for the sapporo-wes spec version. This constant is referenced throughout the codebase to produce the `**sapporo-wes-X.X.X extension:**` markers in OpenAPI descriptions, `info.version`, and example values.

To bump the spec version:

1. Update `SAPPORO_WES_SPEC_VERSION` in `sapporo/config.py`
2. Regenerate the spec: `uv run python -m sapporo.config`
3. Rename the output file if the major/minor version changed

## Release Process

### Version Management

- The `version` field in `pyproject.toml` is the single source of truth
- At runtime, the version is obtained via `importlib.metadata.version("sapporo")`
- Docker image version is injected by CI from the tag name with `--build-arg VERSION=...`

### Release Steps

1. Update `version` in `pyproject.toml` on the `develop` branch and run `uv lock`
2. Create a PR from `develop` to `main` and merge
3. Create a version tag on the `main` branch:

   ```bash
   git checkout main && git pull
   git tag X.Y.Z
   git push origin X.Y.Z
   ```

4. The tag push triggers `release.yml` automatically:
   - Version consistency check (tag == pyproject.toml version)
   - Publish PyPI package (Trusted Publishing)
   - Build and push multi-architecture Docker image (ghcr.io)
   - Create GitHub Release (auto-generated release notes)

### Differences from 1.x

- Changed from Flask to FastAPI
- Updated base GA4GH WES from 1.0.0 to 1.1.0
- Reorganized authentication with switchable methods
- Added SQLite database for faster `GET /runs` queries
- Organized Python and Docker toolchain
- Simplified `executable_workflows.json` to a list of `workflow_url`s
- Full support for automatic run directory cleanup
- See the [sapporo-wes-2.0.0 specification](https://github.com/sapporo-wes/sapporo-service/blob/main/sapporo-wes-spec-2.0.0.yml) for detailed API changes
