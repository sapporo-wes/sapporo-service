"""
CLI tools for sapporo-service.

Usage:
    python -m sapporo.cli hash-password
    python -m sapporo.cli generate-secret
"""
import secrets
import sys
from argparse import ArgumentParser, Namespace
from getpass import getpass

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


def generate_secret(args: Namespace) -> None:  # pylint: disable=unused-argument
    """Generate a cryptographically secure secret key."""
    secret = secrets.token_urlsafe(32)
    print(f"Secret key: {secret}")


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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
