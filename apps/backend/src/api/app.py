"""FastAPI application factory."""

from __future__ import annotations

import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.router import router
from core.logging import bind_log_context, configure_server_logger, reset_log_context
from core.settings import load_api_description, load_api_info, load_settings
from services.runtime import create_lifespan

settings = load_settings()
logger = configure_server_logger(name="segb.server", level=settings.log_level, log_file=settings.log_file)
api_info = load_api_info(settings.api_info_file)
api_description = load_api_description(settings.api_description_file)

app = FastAPI(
    title=api_info["title"],
    description=api_description,
    version=settings.version,
    contact=api_info["contact"],
    license_info=api_info["license"],
    lifespan=create_lifespan(settings=settings, logger=logger),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    if request.client and request.client.host:
        return request.client.host
    return "-"


def _resolve_request_actor(request: Request) -> str | None:
    actor = getattr(request.state, "actor", None)
    return actor if isinstance(actor, str) and actor.strip() else None


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex[:12]
    context_tokens = bind_log_context(
        request_id=request_id,
        actor="anonymous",
        origin_ip=_resolve_client_ip(request),
    )
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        actor = _resolve_request_actor(request)
        actor_tokens = bind_log_context(actor=actor) if actor is not None else {}
        try:
            logger.exception("HTTP %s %s -> 500 (%.1f ms)", request.method, request.url.path, elapsed_ms)
        finally:
            reset_log_context(actor_tokens)
        raise
    else:
        elapsed_ms = (time.perf_counter() - start) * 1000
        actor = _resolve_request_actor(request)
        actor_tokens = bind_log_context(actor=actor) if actor is not None else {}
        try:
            logger.info("HTTP %s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
        finally:
            reset_log_context(actor_tokens)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        reset_log_context(context_tokens)


app.include_router(router)
