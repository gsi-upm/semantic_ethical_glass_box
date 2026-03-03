"""Secure JWT generation CLI for SEGB administrators."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from typing import Sequence
from uuid import uuid4

import jwt

from core.security import ALGORITHM, Role

MIN_SECRET_LENGTH = 32
DEFAULT_TTL_SECONDS = 3600
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 60 * 60 * 24 * 30


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate SEGB JWT tokens securely without passing secrets as CLI arguments.",
    )
    parser.add_argument("--username", required=True, help="Username claim to embed in the token.")
    parser.add_argument("--name", default=None, help="Optional display name claim.")
    parser.add_argument(
        "--role",
        dest="roles",
        action="append",
        required=True,
        choices=[role.value for role in Role],
        help="Role claim. Repeat for multiple roles (e.g. --role admin --role auditor).",
    )
    parser.add_argument(
        "--expires-in",
        type=int,
        default=DEFAULT_TTL_SECONDS,
        help=f"Token TTL in seconds ({MIN_TTL_SECONDS}..{MAX_TTL_SECONDS}).",
    )
    parser.add_argument(
        "--not-before-delay",
        type=int,
        default=0,
        help="Seconds to delay token validity from now (default: 0).",
    )
    parser.add_argument(
        "--secret-env",
        default="SECRET_KEY",
        help="Environment variable used to read the HMAC secret (default: SECRET_KEY).",
    )
    parser.add_argument(
        "--secret-file",
        default=None,
        help="Optional file path containing the secret; overrides --secret-env if provided.",
    )
    parser.add_argument(
        "--allow-weak-secret",
        action="store_true",
        help=f"Allow secrets shorter than {MIN_SECRET_LENGTH} characters (not recommended).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print metadata as JSON (token, claims, and expiration timestamp).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _resolve_secret(*, secret_env: str, secret_file: str | None) -> str:
    if secret_file:
        secret = Path(secret_file).read_text(encoding="utf-8").strip()
        if secret:
            return secret

    env_secret = os.getenv(secret_env, "").strip()
    if env_secret:
        return env_secret

    return getpass(f"Enter signing secret ({secret_env}): ").strip()


def _validate_inputs(args: argparse.Namespace, *, secret: str) -> None:
    if not args.username.strip():
        raise ValueError("--username cannot be empty.")

    if not secret:
        raise ValueError("Signing secret is empty. Provide a non-empty secret via env, file, or prompt.")

    if len(secret) < MIN_SECRET_LENGTH and not args.allow_weak_secret:
        raise ValueError(
            f"Signing secret is too short ({len(secret)} chars). "
            f"Use at least {MIN_SECRET_LENGTH}, or pass --allow-weak-secret if unavoidable."
        )

    if args.expires_in < MIN_TTL_SECONDS or args.expires_in > MAX_TTL_SECONDS:
        raise ValueError(f"--expires-in must be between {MIN_TTL_SECONDS} and {MAX_TTL_SECONDS} seconds.")

    if args.not_before_delay < 0:
        raise ValueError("--not-before-delay must be >= 0.")


def _build_payload(args: argparse.Namespace) -> dict[str, object]:
    now = int(time.time())
    roles = list(dict.fromkeys(args.roles))

    payload: dict[str, object] = {
        "username": args.username.strip(),
        "roles": roles,
        "iat": now,
        "nbf": now + args.not_before_delay,
        "exp": now + args.expires_in,
        "jti": uuid4().hex,
    }
    if args.name:
        payload["name"] = args.name.strip()
    return payload


def _format_exp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        secret = _resolve_secret(secret_env=args.secret_env, secret_file=args.secret_file)
        _validate_inputs(args, secret=secret)
        payload = _build_payload(args)
        token = jwt.encode(payload, secret, algorithm=ALGORITHM)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    if args.json:
        output = {
            "token": token,
            "username": payload["username"],
            "roles": payload["roles"],
            "exp": payload["exp"],
            "exp_utc": _format_exp(int(payload["exp"])),
            "algorithm": ALGORITHM,
        }
        print(json.dumps(output, ensure_ascii=True))
    else:
        print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
