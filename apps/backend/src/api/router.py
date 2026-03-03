"""Top-level router composed from domain-specific routers."""

from __future__ import annotations

from fastapi import APIRouter

from api.routers.graph_ops import router as graph_router
from api.routers.health_auth import router as health_auth_router
from api.routers.shared_context_ops import router as shared_context_router
from api.routers.system_ops import router as system_router

router = APIRouter()
router.include_router(health_auth_router)
router.include_router(graph_router)
router.include_router(shared_context_router)
router.include_router(system_router)

