"""HTTP request bodies for backend API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TTLContent(BaseModel):
    ttl_content: str
    user: str | None = None


class DeleteRequest(BaseModel):
    user: str | None = None


class TtlValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    focus_node: str | None = None
    predicate: str | None = None
    value: str | None = None


class TtlValidationResponse(BaseModel):
    valid: bool
    syntax_ok: bool
    semantic_ok: bool
    triple_count: int
    issues: list[TtlValidationIssue]


class QueryValidationRequest(BaseModel):
    query: str


class QueryValidationResponse(BaseModel):
    valid: bool
    query_kind: str
    allows_update_execution: bool
    message: str


class ServerLogEntry(BaseModel):
    timestamp: str | None = None
    level: str | None = None
    logger: str | None = None
    request_id: str | None = None
    actor: str | None = None
    origin_ip: str | None = None
    message: str
    raw: str


class ServerLogsFilters(BaseModel):
    limit: int
    level: str | None = None
    contains: str | None = None


class ServerLogsResponse(BaseModel):
    log_file: str
    count: int
    filters: ServerLogsFilters
    entries: list[ServerLogEntry]
