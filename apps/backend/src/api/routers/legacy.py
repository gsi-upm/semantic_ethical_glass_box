"""Routes of the 0.4.x API that robot clients still call, kept until 2.0.

``POST /log`` runs the same service and audit path as ``POST /ttl``; its audit entries record the route
``POST /log``, which is how legacy usage is measured (``GET /legacy/usage``). ``GET /health`` is only logged.
"""

from __future__ import annotations

import logging
from typing import Annotated, Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.routing import APIRoute
from rdflib import Graph

from api.deps import get_log_service, require_virtuoso_ready
from api.request_context import build_request_actor, request_actor_context
from api.routers.graph_ops import insert_with_audit
from core.security import Role, User, require_roles, validate_token
from services.log_service import LogService

logger = logging.getLogger("segb.server")

LEGACY_DOC_URL = "https://semantic-ethical-glass-box.readthedocs.io/en/latest/reference/legacy-api/"
DEPRECATION_HEADERS = {
    "Deprecation": "true",
    "Link": f'<{LEGACY_DOC_URL}>; rel="deprecation"; type="text/html"',
}
LEGACY_LOG_ROUTE = "POST /log"


class DeprecatedRoute(APIRoute):
    """Adds the deprecation headers to every response, errors included (401, 403, 422...)."""

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                response = await original(request)
            except HTTPException as error:
                response = JSONResponse(
                    {"detail": error.detail}, status_code=error.status_code, headers=error.headers
                )
            response.headers.update(DEPRECATION_HEADERS)
            return response

        return handler


router = APIRouter(route_class=DeprecatedRoute)
usage_router = APIRouter()


@router.get("/health", response_class=PlainTextResponse, deprecated=True)
async def health(request: Request) -> PlainTextResponse:
    ip = request.client.host if request.client else "-"
    logger.info("Legacy GET /health (ip=%s)", ip)
    return PlainTextResponse(f"SEGB is running. Version {request.app.version}.\n")


@router.post("/log", status_code=201, deprecated=True)
async def save_log(
    request: Request,
    _: Annotated[None, Depends(require_virtuoso_ready)],
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.LOGGER, Role.ADMIN))
    try:
        ttl_content = (await request.body()).decode("utf-8")
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="Body must be UTF-8 Turtle.") from error
    if not ttl_content.strip():
        raise HTTPException(status_code=422, detail="Body must be Turtle (text/turtle).")
    try:
        Graph().parse(data=ttl_content, format="turtle")
    except Exception as error:  # rdflib raises several parser-specific types for bad syntax
        raise HTTPException(status_code=422, detail=f"Invalid Turtle: {str(error).strip() or 'syntax error'}") from error

    logger.info("Legacy POST /log (user=%s)", user.username)
    await insert_with_audit(
        request,
        ttl_content=ttl_content,
        user=user,
        claimed_user=None,
        route=LEGACY_LOG_ROUTE,
        reject_when_busy=False,
    )
    return JSONResponse({"message": "Log saved successfully"}, status_code=201)


@usage_router.get("/legacy/usage")
async def legacy_usage(
    request: Request,
    _: Annotated[None, Depends(require_virtuoso_ready)],
    user: Annotated[User, Depends(validate_token)],
):
    """How often the legacy upload route was used, counted over the audit graph (survives restarts)."""
    require_roles(user, allowed=(Role.ADMIN,))
    service: LogService = get_log_service(request)
    request_actor = build_request_actor(request, user.username)
    with request_actor_context(request, request_actor):
        usage = service.route_usage(LEGACY_LOG_ROUTE, actor=request_actor.actor, origin_ip=request_actor.origin_ip)
    return JSONResponse(
        {"routes": {LEGACY_LOG_ROUTE: usage}, "not_counted": ["GET /health (logged only, never audited)"]}
    )
