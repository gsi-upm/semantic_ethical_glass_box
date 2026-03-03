import asyncio
import time
import unittest
from unittest.mock import patch

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import core.security as security


class TestSecurityValidation(unittest.TestCase):
    @staticmethod
    def _make_credentials(payload: dict[str, object], *, secret: str) -> HTTPAuthorizationCredentials:
        token = jwt.encode(payload, secret, algorithm=security.ALGORITHM)
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    def test_no_auth_mode_grants_all_roles(self) -> None:
        with patch.object(security, "SECRET_KEY", None):
            user = asyncio.run(security.validate_token(None))

        self.assertEqual(user.username, "anonymous_user")
        self.assertCountEqual(user.roles, [role.value for role in security.Role])

    def test_requires_authorization_header_when_auth_enabled(self) -> None:
        with patch.object(security, "SECRET_KEY", "x" * 32):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(security.validate_token(None))

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "Authorization header is required")

    def test_rejects_missing_required_claim(self) -> None:
        secret = "x" * 32
        payload = {
            "username": "demo_admin",
            "roles": ["admin"],
            "iat": int(time.time()),
        }
        credentials = self._make_credentials(payload, secret=secret)

        with patch.object(security, "SECRET_KEY", secret):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(security.validate_token(credentials))

        self.assertEqual(context.exception.status_code, 401)
        self.assertIn("Missing claim: exp", context.exception.detail)

    def test_rejects_unknown_role(self) -> None:
        secret = "x" * 32
        now = int(time.time())
        payload = {
            "username": "demo_admin",
            "roles": ["superadmin"],
            "iat": now,
            "nbf": now,
            "exp": now + 600,
        }
        credentials = self._make_credentials(payload, secret=secret)

        with patch.object(security, "SECRET_KEY", secret):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(security.validate_token(credentials))

        self.assertEqual(context.exception.status_code, 401)
        self.assertIn("role is not allowed", context.exception.detail)

    def test_accepts_valid_role_and_claims(self) -> None:
        secret = "x" * 32
        now = int(time.time())
        payload = {
            "username": "robot_logger",
            "roles": ["logger"],
            "iat": now,
            "nbf": now,
            "exp": now + 600,
        }
        credentials = self._make_credentials(payload, secret=secret)

        with patch.object(security, "SECRET_KEY", secret):
            user = asyncio.run(security.validate_token(credentials))

        self.assertEqual(user.username, "robot_logger")
        self.assertEqual(user.roles, ["logger"])


if __name__ == "__main__":
    unittest.main()

