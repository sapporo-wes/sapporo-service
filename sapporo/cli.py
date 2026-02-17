"""CLI tools for sapporo-service.

Usage:
    sapporo-cli hash-password
    sapporo-cli generate-secret
    sapporo-cli generate-ro-crate <run_dir>
    sapporo-cli dump-outputs <run_dir>
    sapporo-cli generate-openapi [--output <path>]
"""

import secrets
import sys
from argparse import ArgumentParser, Namespace
from getpass import getpass
from pathlib import Path

from argon2 import PasswordHasher


def hash_password(args: Namespace) -> None:
    """Hash a password using argon2."""
    if args.password:
        password = args.password
    else:
        password = getpass("Enter password: ")
        password_confirm = getpass("Confirm password: ")
        if password != password_confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    hasher = PasswordHasher()
    password_hash = hasher.hash(password)
    print(f"Password hash: {password_hash}")


def generate_secret(_args: Namespace) -> None:
    """Generate a cryptographically secure secret key."""
    secret = secrets.token_urlsafe(32)
    print(f"Secret key: {secret}")


def _validate_run_dir(run_dir_str: str) -> Path:
    """Validate that the given path is an existing directory."""
    run_dir = Path(run_dir_str).resolve()
    if not run_dir.exists():
        print(f"Error: '{run_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not run_dir.is_dir():
        print(f"Error: '{run_dir}' is not a directory.", file=sys.stderr)
        sys.exit(1)
    return run_dir


def generate_ro_crate(args: Namespace) -> None:
    """Generate RO-Crate metadata for the given run directory."""
    run_dir = _validate_run_dir(args.run_dir)

    from sapporo.ro_crate import generate_ro_crate as _generate_ro_crate

    _generate_ro_crate(str(run_dir))


def dump_outputs(args: Namespace) -> None:
    """Dump outputs list for the given run directory."""
    run_dir = _validate_run_dir(args.run_dir)

    from sapporo.run import dump_outputs_list

    dump_outputs_list(str(run_dir))


def generate_openapi(args: Namespace) -> None:
    """Generate OpenAPI specification file."""
    original_argv = sys.argv
    sys.argv = ["sapporo"]
    try:
        from sapporo.app import create_app
        from sapporo.config import SAPPORO_WES_SPEC_VERSION, dump_openapi_schema

        app = create_app()
        schema_yaml = dump_openapi_schema(app)

        if args.output:
            output_path = Path(args.output)
        else:
            output_path = Path(f"openapi/sapporo-wes-spec-{SAPPORO_WES_SPEC_VERSION}.yml")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(schema_yaml, encoding="utf-8")
        print(f"OpenAPI spec written to: {output_path}")
    finally:
        sys.argv = original_argv


def main() -> None:
    parser = ArgumentParser(
        description="CLI tools for sapporo-service.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # hash-password command
    hash_parser = subparsers.add_parser(
        "hash-password",
        help="Hash a password using argon2.",
    )
    hash_parser.add_argument(
        "--password",
        type=str,
        help="Password to hash. If not provided, will prompt interactively.",
    )
    hash_parser.set_defaults(func=hash_password)

    # generate-secret command
    secret_parser = subparsers.add_parser(
        "generate-secret",
        help="Generate a cryptographically secure secret key.",
    )
    secret_parser.set_defaults(func=generate_secret)

    # generate-ro-crate command
    ro_crate_parser = subparsers.add_parser(
        "generate-ro-crate",
        help="Generate RO-Crate metadata for a run directory.",
    )
    ro_crate_parser.add_argument(
        "run_dir",
        type=str,
        help="Path to the run directory.",
    )
    ro_crate_parser.set_defaults(func=generate_ro_crate)

    # dump-outputs command
    dump_outputs_parser = subparsers.add_parser(
        "dump-outputs",
        help="Dump outputs list for a run directory.",
    )
    dump_outputs_parser.add_argument(
        "run_dir",
        type=str,
        help="Path to the run directory.",
    )
    dump_outputs_parser.set_defaults(func=dump_outputs)

    # generate-openapi command
    openapi_parser = subparsers.add_parser(
        "generate-openapi",
        help="Generate OpenAPI specification file.",
    )
    openapi_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path. Defaults to openapi/sapporo-wes-spec-<VERSION>.yml.",
    )
    openapi_parser.set_defaults(func=generate_openapi)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
