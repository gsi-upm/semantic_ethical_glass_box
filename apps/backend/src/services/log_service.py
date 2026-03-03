"""Application service for TTL workflows."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from services.ports import GraphStorePort
from services.ttl_validation import validate_ttl_content

logger = logging.getLogger("segb.server")


@dataclass(slots=True)
class LogService:
    virtuoso: GraphStorePort

    def validate_ttl(self, *, ttl_content: str, actor: str, origin_ip: str) -> dict:
        logger.info(
            "TTL validation requested (actor=%s, ip=%s, bytes=%d)",
            actor,
            origin_ip,
            len(ttl_content.encode("utf-8")),
        )
        result = validate_ttl_content(ttl_content)
        logger.info(
            "TTL validation completed (actor=%s, ip=%s, valid=%s, syntax_ok=%s, semantic_ok=%s, triples=%d, issues=%d)",
            actor,
            origin_ip,
            result.valid,
            result.syntax_ok,
            result.semantic_ok,
            result.triple_count,
            len(result.issues),
        )
        return result.to_payload()

    def insert_ttl(self, *, ttl_content: str, actor: str, origin_ip: str) -> dict:
        """Persists TTL data in Virtuoso and emits operational logs."""
        logger.info(
            "TTL insert requested (actor=%s, ip=%s, bytes=%d)",
            actor,
            origin_ip,
            len(ttl_content.encode("utf-8")),
        )
        log_id = self.virtuoso.insert_ttl(ttl_content)
        logger.info("TTL insert completed (actor=%s, ip=%s, log_id=%s)", actor, origin_ip, log_id)
        return {"message": "TTL inserted into Virtuoso", "log_id": log_id}

    def get_events_ttl(self, *, actor: str, origin_ip: str) -> str:
        logger.info("TTL export requested (actor=%s, ip=%s)", actor, origin_ip)
        ttl_text = self.virtuoso.get_ttls()
        logger.info(
            "TTL export completed (actor=%s, ip=%s, bytes=%d)",
            actor,
            origin_ip,
            len(ttl_text.encode("utf-8")),
        )
        return ttl_text

    def execute_query(self, *, query: str, actor: str, origin_ip: str) -> str:
        query_preview = " ".join(query.split())
        if len(query_preview) > 160:
            query_preview = f"{query_preview[:157]}..."

        logger.info(
            "SPARQL query requested (actor=%s, ip=%s, query='%s')",
            actor,
            origin_ip,
            query_preview,
        )
        result_ttl = self.virtuoso.run_custom_query(query, allow_updates=False)
        logger.info(
            "SPARQL query completed (actor=%s, ip=%s, bytes=%d)",
            actor,
            origin_ip,
            len(result_ttl.encode("utf-8")),
        )
        return result_ttl

    def validate_query(self, *, query: str, actor: str, origin_ip: str) -> dict:
        query_preview = " ".join(query.split())
        if len(query_preview) > 160:
            query_preview = f"{query_preview[:157]}..."

        logger.info(
            "SPARQL validation requested (actor=%s, ip=%s, query='%s')",
            actor,
            origin_ip,
            query_preview,
        )
        result = self.virtuoso.validate_query(query, allow_updates=False)
        logger.info(
            "SPARQL validation completed (actor=%s, ip=%s, valid=%s, kind=%s)",
            actor,
            origin_ip,
            result.get("valid"),
            result.get("query_kind"),
        )
        return result

    def delete_all_ttls(self, *, actor: str, origin_ip: str) -> dict:
        """Deletes graph content in Virtuoso and emits operational logs."""
        logger.warning("TTL delete-all requested (actor=%s, ip=%s)", actor, origin_ip)
        ttl_text = self.virtuoso.get_ttls()

        if not ttl_text.strip():
            logger.info("Delete-all skipped because graph is empty (actor=%s, ip=%s)", actor, origin_ip)
            return {"message": "No TTLs to delete"}

        self.virtuoso.delete_all_triples()
        logger.warning("Graph cleared by delete-all (actor=%s, ip=%s)", actor, origin_ip)
        return {"message": "Graph cleared."}
