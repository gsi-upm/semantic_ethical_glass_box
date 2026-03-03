import argparse
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools.generate_jwt import (
    MIN_SECRET_LENGTH,
    _build_payload,
    _resolve_secret,
    _validate_inputs,
    main,
)


def _args(**overrides: object) -> argparse.Namespace:
    data = {
        "username": "admin_user",
        "name": "Admin User",
        "roles": ["admin"],
        "expires_in": 3600,
        "not_before_delay": 0,
        "secret_env": "SECRET_KEY",
        "secret_file": None,
        "allow_weak_secret": False,
        "json": False,
    }
    data.update(overrides)
    return argparse.Namespace(**data)


class TestGenerateJwtTool(unittest.TestCase):
    def test_resolve_secret_prefers_secret_file_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            secret_file = Path(tmp_dir) / "secret.txt"
            secret_file.write_text("from_file_secret_value\n", encoding="utf-8")
            with patch.dict(os.environ, {"SECRET_KEY": "from_env_secret_value"}, clear=False):
                resolved = _resolve_secret(secret_env="SECRET_KEY", secret_file=str(secret_file))

        self.assertEqual(resolved, "from_file_secret_value")

    def test_validate_inputs_rejects_weak_secret_without_override(self) -> None:
        args = _args()
        with self.assertRaisesRegex(ValueError, "too short"):
            _validate_inputs(args, secret="x" * (MIN_SECRET_LENGTH - 1))

    def test_build_payload_deduplicates_roles(self) -> None:
        args = _args(roles=["admin", "admin", "auditor"])
        uuid_mock = Mock()
        uuid_mock.hex = "fixed-jti"
        with patch("tools.generate_jwt.time.time", return_value=1_700_000_000), patch(
            "tools.generate_jwt.uuid4",
            return_value=uuid_mock,
        ):
            payload = _build_payload(args)

        self.assertEqual(payload["username"], "admin_user")
        self.assertEqual(payload["roles"], ["admin", "auditor"])
        self.assertEqual(payload["iat"], 1_700_000_000)
        self.assertEqual(payload["nbf"], 1_700_000_000)
        self.assertEqual(payload["exp"], 1_700_003_600)
        self.assertEqual(payload["jti"], "fixed-jti")

    def test_main_returns_error_code_when_inputs_are_invalid(self) -> None:
        args = _args(allow_weak_secret=False)
        with (
            patch("tools.generate_jwt._parse_args", return_value=args),
            patch("tools.generate_jwt._resolve_secret", return_value="short"),
            patch("tools.generate_jwt.print") as print_mock,
        ):
            code = main([])

        self.assertEqual(code, 2)
        print_mock.assert_called()

    def test_main_prints_json_when_requested(self) -> None:
        args = _args(json=True)
        payload = {
            "username": "admin_user",
            "roles": ["admin"],
            "iat": 1_700_000_000,
            "nbf": 1_700_000_000,
            "exp": 1_700_003_600,
            "jti": "fixed-jti",
        }
        with (
            patch("tools.generate_jwt._parse_args", return_value=args),
            patch("tools.generate_jwt._resolve_secret", return_value="x" * MIN_SECRET_LENGTH),
            patch("tools.generate_jwt._build_payload", return_value=payload),
            patch("tools.generate_jwt.jwt.encode", return_value="jwt-token-123"),
            patch("tools.generate_jwt.print") as print_mock,
        ):
            code = main([])

        self.assertEqual(code, 0)
        print_mock.assert_called_once()
        output = json.loads(print_mock.call_args.args[0])
        self.assertEqual(output["token"], "jwt-token-123")
        self.assertEqual(output["username"], "admin_user")
        self.assertEqual(output["roles"], ["admin"])
        self.assertEqual(output["algorithm"], "HS256")


if __name__ == "__main__":
    unittest.main()
