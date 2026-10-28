"""Logging utilities for backend bootstrap."""

from __future__ import annotations

from contextvars import ContextVar, Token
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

DEFAULT_LOGS_DIR = Path("/logs")
FALLBACK_LOGS_DIR = Path("/tmp/segb-logs")
LOGS_DIR_ENV = "SERVER_LOG_DIR"

_REQUEST_ID_CONTEXT: ContextVar[str] = ContextVar("request_id", default="-")
_ACTOR_CONTEXT: ContextVar[str] = ContextVar("actor", default="-")
_ORIGIN_IP_CONTEXT: ContextVar[str] = ContextVar("origin_ip", default="-")


def _candidate_logs_dirs() -> list[Path]:
    env_value = os.getenv(LOGS_DIR_ENV)
    candidates: list[Path] = []
    if env_value and env_value.strip():
        candidates.append(Path(env_value.strip()).expanduser())
    candidates.append(DEFAULT_LOGS_DIR)
    candidates.append(Path.cwd() / "logs")
    candidates.append(FALLBACK_LOGS_DIR)
    return candidates


def _dir_is_writable(candidate: Path) -> bool:
    probe_file = candidate / ".segb_write_probe"
    try:
        with probe_file.open("a", encoding="utf-8"):
            pass
        probe_file.unlink(missing_ok=True)
        return True
    except OSError:
        try:
            probe_file.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _resolve_logs_dir() -> Path:
    last_error: OSError | None = None
    seen: set[str] = set()
    for candidate in _candidate_logs_dirs():
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if not _dir_is_writable(candidate):
                last_error = PermissionError(f"Logs directory is not writable: {candidate}")
                continue
            return candidate
        except OSError as error:
            last_error = error
            continue

    if last_error is not None:
        raise last_error
    raise OSError("Could not resolve a writable logs directory.")


class RequestContextFilter(logging.Filter):
    """Injects request-scoped context into each log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _REQUEST_ID_CONTEXT.get()
        record.actor = _ACTOR_CONTEXT.get()
        record.origin_ip = _ORIGIN_IP_CONTEXT.get()
        return True


def resolve_log_file_path(log_file: str) -> Path:
    logs_dir = _resolve_logs_dir()
    return logs_dir / log_file


def bind_log_context(
    *,
    request_id: str | None = None,
    actor: str | None = None,
    origin_ip: str | None = None,
) -> dict[str, Token[str]]:
    tokens: dict[str, Token[str]] = {}
    if request_id is not None:
        tokens["request_id"] = _REQUEST_ID_CONTEXT.set(request_id)
    if actor is not None:
        tokens["actor"] = _ACTOR_CONTEXT.set(actor)
    if origin_ip is not None:
        tokens["origin_ip"] = _ORIGIN_IP_CONTEXT.set(origin_ip)
    return tokens


def reset_log_context(tokens: dict[str, Token[str]]) -> None:
    request_token = tokens.get("request_id")
    if request_token is not None:
        _REQUEST_ID_CONTEXT.reset(request_token)

    actor_token = tokens.get("actor")
    if actor_token is not None:
        _ACTOR_CONTEXT.reset(actor_token)

    origin_ip_token = tokens.get("origin_ip")
    if origin_ip_token is not None:
        _ORIGIN_IP_CONTEXT.reset(origin_ip_token)


def configure_server_logger(*, name: str, level: str, log_file: str) -> logging.Logger:
    """Creates a file+stream logger with request context and log rotation."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    if logger.handlers:
        return logger

    log_path = resolve_log_file_path(log_file)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | rid=%(request_id)s actor=%(actor)s ip=%(origin_ip)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    context_filter = RequestContextFilter()

    file_handler = RotatingFileHandler(
        log_path,
        mode="a",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
