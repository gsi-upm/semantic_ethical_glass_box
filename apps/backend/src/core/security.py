"""Authentication and authorization helpers."""

from __future__ import annotations

import os
from enum import Enum
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


class Role(str, Enum):
    AUDITOR = "auditor"
    LOGGER = "logger"
    ADMIN = "admin"


class User(BaseModel):
    username: str
    name: str | None = None
    roles: list[str]
    exp: int | None = None


SECRET_KEY = os.getenv("SECRET_KEY") or None
ALGORITHM = "HS256"
security = HTTPBearer(auto_error=False)
REQUIRED_TOKEN_CLAIMS = ("username", "roles", "exp")


def _raise_invalid_token(message: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _validate_decoded_claims(decoded: dict[str, object]) -> None:
    username = decoded.get("username")
    if not isinstance(username, str) or not username.strip():
        _raise_invalid_token("Could not validate credentials. Invalid Token: username claim is invalid")

    roles = decoded.get("roles")
    if not isinstance(roles, list) or not roles:
        _raise_invalid_token("Could not validate credentials. Invalid Token: roles claim is invalid")

    allowed_roles = {role.value for role in Role}
    for role in roles:
        if not isinstance(role, str) or role not in allowed_roles:
            _raise_invalid_token("Could not validate credentials. Invalid Token: role is not allowed")


async def validate_token(
    auth_credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> User:
    """Validates JWT token when security is enabled, otherwise grants all roles (local no-auth mode)."""
    if not SECRET_KEY:
        return User(
            username="anonymous_user",
            name="Unknown User - No Security Enabled",
            roles=[role.value for role in Role],
            exp=None,
        )

    if auth_credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        decoded = jwt.decode(
            auth_credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": list(REQUIRED_TOKEN_CLAIMS)},
        )
        _validate_decoded_claims(decoded)
        return User(**decoded)
    except jwt.MissingRequiredClaimError as error:
        _raise_invalid_token(f"Could not validate credentials. Missing claim: {error.claim}")
    except jwt.ExpiredSignatureError:
        _raise_invalid_token("Could not validate credentials. Expired Token")
    except jwt.InvalidTokenError:
        _raise_invalid_token("Could not validate credentials. Invalid Token")


def require_roles(user: User, *, allowed: tuple[Role, ...]) -> None:
    """Checks that the user contains at least one allowed role."""
    allowed_values = {role.value for role in allowed}
    if not any(role in allowed_values for role in user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have permission to perform this action",
        )
