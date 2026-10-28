"""System/operational endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.request_context import build_request_actor, request_actor_context
from api.schemas import ServerLogsResponse
from core.logging import resolve_log_file_path
from core.security import Role, User, require_roles, validate_token
from core.settings import load_settings
from services.system_log_service import InvalidLogLevelError, SystemLogService

router = APIRouter()
settings = load_settings()


@router.get("/logs/server", response_model=ServerLogsResponse)
async def get_server_logs(
    request: Request,
    user: Annotated[User, Depends(validate_token)],
    limit: int = Query(default=200, ge=1, le=2000),
    level: str | None = Query(default=None),
    contains: str | None = Query(default=None),
):
    require_roles(user, allowed=(Role.ADMIN,))
    request_actor = build_request_actor(request, user.username)
    service = SystemLogService(log_path=resolve_log_file_path(settings.log_file))
    with request_actor_context(request, request_actor):
        try:
            return service.read_server_logs(limit=limit, level=level, contains=contains)
        except InvalidLogLevelError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

