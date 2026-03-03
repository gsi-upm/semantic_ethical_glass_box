"""Shared-context resolver endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_shared_context_service
from api.request_context import build_request_actor, request_actor_context
from core.security import Role, User, require_roles, validate_token
from services.shared_context_service import SharedContextService
from utils.shared_context import (
    SharedContextReviewAcceptRequest,
    SharedContextReviewDecisionResponse,
    SharedContextReviewQueueResponse,
    SharedContextReconcileResponse,
    SharedContextResolveRequest,
    SharedContextResolveResponse,
)

router = APIRouter()


@router.post("/shared-context/resolve", response_model=SharedContextResolveResponse)
async def resolve_shared_context(
    request: Request,
    data: SharedContextResolveRequest,
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.LOGGER, Role.ADMIN))
    service: SharedContextService = get_shared_context_service(request)
    request_actor = build_request_actor(request, user.username)

    with request_actor_context(request, request_actor):
        try:
            return service.resolve(data)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/shared-context/reconcile", response_model=SharedContextReconcileResponse)
async def reconcile_shared_context(
    request: Request,
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.ADMIN,))
    service: SharedContextService = get_shared_context_service(request)
    request_actor = build_request_actor(request, user.username)

    with request_actor_context(request, request_actor):
        return service.reconcile()


@router.get("/shared-context/stats")
async def shared_context_stats(
    request: Request,
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.AUDITOR, Role.ADMIN))
    service: SharedContextService = get_shared_context_service(request)
    request_actor = build_request_actor(request, user.username)

    with request_actor_context(request, request_actor):
        return service.stats()


@router.get("/shared-context/review/pending", response_model=SharedContextReviewQueueResponse)
async def shared_context_review_pending(
    request: Request,
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.ADMIN,))
    service: SharedContextService = get_shared_context_service(request)
    request_actor = build_request_actor(request, user.username)

    with request_actor_context(request, request_actor):
        return service.review_queue()


@router.post("/shared-context/review/{case_id}/accept", response_model=SharedContextReviewDecisionResponse)
async def shared_context_review_accept(
    case_id: str,
    data: SharedContextReviewAcceptRequest,
    request: Request,
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.ADMIN,))
    service: SharedContextService = get_shared_context_service(request)
    request_actor = build_request_actor(request, user.username)

    with request_actor_context(request, request_actor):
        try:
            return service.accept_review_case(case_id=case_id, target_context_uri=data.target_context_uri)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/shared-context/review/{case_id}/reject", response_model=SharedContextReviewDecisionResponse)
async def shared_context_review_reject(
    case_id: str,
    request: Request,
    user: Annotated[User, Depends(validate_token)],
):
    require_roles(user, allowed=(Role.ADMIN,))
    service: SharedContextService = get_shared_context_service(request)
    request_actor = build_request_actor(request, user.username)

    with request_actor_context(request, request_actor):
        try:
            return service.reject_review_case(case_id=case_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

