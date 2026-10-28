"""Server log reader service for admin observability."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import logging
from pathlib import Path
import re

logger = logging.getLogger("segb.server")

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| "
    r"(?P<level>[A-Z]+) \| "
    r"(?P<logger>[^|]+) \| "
    r"rid=(?P<request_id>\S+) actor=(?P<actor>\S+) ip=(?P<origin_ip>\S+) \| "
    r"(?P<message>.*)$"
)
VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class InvalidLogLevelError(ValueError):
    """Raised when log level filters are invalid."""


@dataclass(slots=True)
class SystemLogService:
    log_path: Path

    def read_server_logs(self, *, limit: int, level: str | None, contains: str | None) -> dict:
        if limit < 1:
            raise ValueError("limit must be >= 1")

        normalized_level: str | None = None
        if level is not None and level.strip():
            normalized_level = level.strip().upper()
            if normalized_level not in VALID_LEVELS:
                supported = ", ".join(sorted(VALID_LEVELS))
                raise InvalidLogLevelError(f"Invalid level '{level}'. Use one of: {supported}.")

        contains_filter = contains.strip() if contains else ""
        contains_filter_lc = contains_filter.lower()

        if not self.log_path.exists():
            return {
                "log_file": str(self.log_path),
                "count": 0,
                "filters": {
                    "limit": limit,
                    "level": normalized_level,
                    "contains": contains_filter or None,
                },
                "entries": [],
            }

        entries_buffer: deque[dict[str, str | None]] = deque(maxlen=limit)
        current_entry: dict[str, str | None] | None = None
        with self.log_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                raw = raw_line.rstrip("\n")
                if not raw:
                    continue

                parsed = self._parse_line(raw)
                if self._is_structured_entry(parsed):
                    if self._entry_matches_filters(
                        current_entry,
                        normalized_level=normalized_level,
                        contains_filter_lc=contains_filter_lc,
                    ):
                        entries_buffer.append(current_entry)
                    current_entry = parsed
                    continue

                if current_entry is None:
                    current_entry = parsed
                    continue

                self._append_continuation_line(current_entry, raw)

        if self._entry_matches_filters(
            current_entry,
            normalized_level=normalized_level,
            contains_filter_lc=contains_filter_lc,
        ):
            entries_buffer.append(current_entry)

        logger.info(
            "Server logs read (path=%s, returned=%d, level=%s, contains=%s)",
            self.log_path,
            len(entries_buffer),
            normalized_level or "-",
            contains_filter or "-",
        )
        return {
            "log_file": str(self.log_path),
            "count": len(entries_buffer),
            "filters": {
                "limit": limit,
                "level": normalized_level,
                "contains": contains_filter or None,
            },
            "entries": list(entries_buffer),
        }

    @staticmethod
    def _is_structured_entry(entry: dict[str, str | None]) -> bool:
        return (
            entry["timestamp"] is not None
            and entry["level"] is not None
            and entry["logger"] is not None
        )

    @staticmethod
    def _append_continuation_line(entry: dict[str, str | None], raw_line: str) -> None:
        message = entry.get("message") or ""
        entry["message"] = f"{message}\n{raw_line}" if message else raw_line

        raw = entry.get("raw") or ""
        entry["raw"] = f"{raw}\n{raw_line}" if raw else raw_line

    @staticmethod
    def _entry_matches_filters(
        entry: dict[str, str | None] | None,
        *,
        normalized_level: str | None,
        contains_filter_lc: str,
    ) -> bool:
        if entry is None:
            return False
        if normalized_level and entry["level"] != normalized_level:
            return False
        if contains_filter_lc and contains_filter_lc not in (entry["raw"] or "").lower():
            return False
        return True

    def _parse_line(self, raw_line: str) -> dict[str, str | None]:
        match = LOG_PATTERN.match(raw_line)
        if match:
            groups = match.groupdict()
            return {
                "timestamp": groups["timestamp"],
                "level": groups["level"],
                "logger": groups["logger"].strip(),
                "request_id": groups["request_id"],
                "actor": groups["actor"],
                "origin_ip": groups["origin_ip"],
                "message": groups["message"],
                "raw": raw_line,
            }

        return {
            "timestamp": None,
            "level": None,
            "logger": None,
            "request_id": None,
            "actor": None,
            "origin_ip": None,
            "message": raw_line,
            "raw": raw_line,
        }
