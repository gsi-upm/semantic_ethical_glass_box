"""Graph ingestion/query endpoints."""

from __future__ import annotations

from asyncio import Lock
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from api.deps import get_log_service, require_virtuoso_ready
from api.request_context import build_request_actor, request_actor_context
from api.schemas import DeleteRequest, QueryValidationRequest, QueryValidationResponse, TTLContent, TtlValidationResponse
from core.security import Role, User, require_roles, validate_token
from services.log_service import LogService
from utils.audit import AuditContext

router = APIRouter()
transaction_lock = Lock()


@router.post("/ttl/validate", response_model=TtlValidationResponse)
async def validate_ttl(
    request: Request,
    data: TTLContent,
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.ADMIN,))
    service: LogService = get_log_service(request)
    request_actor = build_request_actor(request, data.user, user.username)
    with request_actor_context(request, request_actor):
        return service.validate_ttl(
            ttl_content=data.ttl_content,
            actor=request_actor.actor,
            origin_ip=request_actor.origin_ip,
        )


async def insert_with_audit(
    request: Request,
    *,
    ttl_content: str,
    user: User,
    claimed_user: str | None,
    route: str,
    reject_when_busy: bool,
) -> dict:
    """Stores a TTL upload and its audit entry; shared by ``POST /ttl`` and the legacy ``POST /log``."""
    require_roles(user, allowed=(Role.LOGGER, Role.ADMIN))

    if reject_when_busy and transaction_lock.locked():
        raise HTTPException(status_code=429, detail="Another transaction is in progress. Please try again later.")

    service: LogService = get_log_service(request)
    request_actor = build_request_actor(request, claimed_user, user.username)

    async with transaction_lock:
        with request_actor_context(request, request_actor):
            return service.insert_ttl(
                ttl_content=ttl_content,
                actor=request_actor.actor,
                origin_ip=request_actor.origin_ip,
                audit=AuditContext(
                    username=user.username,
                    roles=tuple(user.roles),
                    origin_ip=request_actor.origin_ip,
                    route=route,
                ),
            )


@router.post("/ttl")
async def insert_ttl(
    request: Request,
    data: TTLContent,
    _: Annotated[None, Depends(require_virtuoso_ready)],
    user: Annotated[User, Depends(validate_token)],
):
    response = await insert_with_audit(
        request,
        ttl_content=data.ttl_content,
        user=user,
        claimed_user=data.user,
        route="POST /ttl",
        reject_when_busy=True,
    )
    return JSONResponse(content=response, status_code=201)


@router.get("/events", response_class=PlainTextResponse)
async def get_events(
    request: Request,
    _: Annotated[None, Depends(require_virtuoso_ready)],
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.AUDITOR, Role.ADMIN))
    service: LogService = get_log_service(request)
    request_actor = build_request_actor(request, user.username)

    with request_actor_context(request, request_actor):
        ttl_text = service.get_events_ttl(actor=request_actor.actor, origin_ip=request_actor.origin_ip)

    return PlainTextResponse(content=ttl_text, media_type="text/turtle")


@router.get("/query", response_class=PlainTextResponse)
async def execute_query(
    request: Request,
    query: str,
    _: Annotated[None, Depends(require_virtuoso_ready)],
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.AUDITOR, Role.ADMIN))
    service: LogService = get_log_service(request)
    request_actor = build_request_actor(request, user.username)

    with request_actor_context(request, request_actor):
        try:
            result = service.execute_query(query=query, actor=request_actor.actor, origin_ip=request_actor.origin_ip)
        except (PermissionError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return PlainTextResponse(content=result, media_type="text/turtle")


@router.post("/query/validate", response_model=QueryValidationResponse)
async def validate_query(
    request: Request,
    data: QueryValidationRequest,
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.AUDITOR, Role.ADMIN))
    service: LogService = get_log_service(request)
    request_actor = build_request_actor(request, user.username)

    with request_actor_context(request, request_actor):
        return service.validate_query(query=data.query, actor=request_actor.actor, origin_ip=request_actor.origin_ip)


@router.post("/ttl/delete_all")
async def delete_all_ttls(
    request: Request,
    data: DeleteRequest,
    _: Annotated[None, Depends(require_virtuoso_ready)],
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.ADMIN,))

    if transaction_lock.locked():
        raise HTTPException(status_code=429, detail="Another transaction is in progress. Please try again later.")

    service: LogService = get_log_service(request)
    request_actor = build_request_actor(request, data.user, user.username)

    # Same lock as inserts: nothing can be added between the dump stored in the audit entry and the clear.
    async with transaction_lock:
        with request_actor_context(request, request_actor):
            result = service.delete_all_ttls(
                actor=request_actor.actor,
                origin_ip=request_actor.origin_ip,
                audit=AuditContext(
                    username=user.username,
                    roles=tuple(user.roles),
                    origin_ip=request_actor.origin_ip,
                    route="POST /ttl/delete_all",
                ),
            )

    return JSONResponse(content=result, status_code=200)


@router.get("/history")
async def get_history(
    request: Request,
    _: Annotated[None, Depends(require_virtuoso_ready)],
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.AUDITOR, Role.ADMIN))
    service: LogService = get_log_service(request)
    request_actor = build_request_actor(request, user.username)

    with request_actor_context(request, request_actor):
        history = service.audit_history(actor=request_actor.actor, origin_ip=request_actor.origin_ip)

    return JSONResponse(content=history, status_code=200)


@router.get("/log")
async def get_log(
    request: Request,
    _: Annotated[None, Depends(require_virtuoso_ready)],
    user: Annotated[User, Depends(validate_token)],
    log_id: str | None = None,
):
    require_roles(user, allowed=(Role.AUDITOR, Role.ADMIN))
    if not log_id:
        raise HTTPException(status_code=400, detail="Not received data or invalid data")

    service: LogService = get_log_service(request)
    request_actor = build_request_actor(request, user.username)

    with request_actor_context(request, request_actor):
        entry = service.audit_entry(log_id=log_id, actor=request_actor.actor, origin_ip=request_actor.origin_ip)

    if entry is None:
        raise HTTPException(status_code=404, detail="Log info not found")
    return JSONResponse(content=entry, status_code=200)
