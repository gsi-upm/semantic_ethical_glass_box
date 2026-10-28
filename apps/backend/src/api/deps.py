"""FastAPI dependencies for accessing runtime services."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from services.log_service import LogService
from services.runtime import RuntimeServices
from services.shared_context_service import SharedContextService


def get_services(request: Request) -> RuntimeServices:
    services: RuntimeServices = request.app.state.services
    return services


def get_log_service(request: Request) -> LogService:
    services = get_services(request)
    return LogService(virtuoso=services.virtuoso)


def get_shared_context_service(request: Request) -> SharedContextService:
    services = get_services(request)
    return SharedContextService(resolver=services.shared_context)


def require_virtuoso_ready(request: Request) -> None:
    services = get_services(request)
    if not services.virtuoso_ok:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Virtuoso is unavailable")
