"""Health and auth-mode endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from api.deps import get_services
from core.security import SECRET_KEY
from services.runtime import RuntimeServices

router = APIRouter()


@router.get("/healthz/live")
def live() -> dict[str, bool]:
    return {"live": True}


@router.get("/healthz/ready")
def ready(request: Request) -> dict[str, bool]:
    services: RuntimeServices = get_services(request)
    return {
        "ready": services.virtuoso_ok,
        "virtuoso": services.virtuoso_ok,
    }


@router.get("/auth/mode")
def auth_mode() -> dict[str, bool]:
    return {"auth_enabled": bool(SECRET_KEY)}

