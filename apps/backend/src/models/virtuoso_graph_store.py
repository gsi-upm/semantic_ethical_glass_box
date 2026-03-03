"""Adapter that exposes VirtuosoModel through the GraphStorePort contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models.virtuoso_model import VirtuosoModel
from services.ports import GraphStorePort


@dataclass(slots=True)
class VirtuosoGraphStoreAdapter(GraphStorePort):
    """Thin adapter so services depend on a port, not a concrete model class."""

    client: VirtuosoModel

    def connect_to_db(self, retries: int = 10, delay: float = 5.0) -> Any:
        return self.client.connect_to_db(retries=retries, delay=delay)

    def close_connection(self) -> None:
        self.client.close_connection()

    def ping(self, timeout_s: float = 1.0) -> bool:
        return self.client.ping(timeout_s=timeout_s)

    def insert_ttl(self, ttl_content: str) -> str:
        return self.client.insert_ttl(ttl_content)

    def get_ttls(self) -> str:
        return self.client.get_ttls()

    def validate_query(self, query: str, *, allow_updates: bool = False) -> dict[str, Any]:
        return self.client.validate_query(query, allow_updates=allow_updates)

    def run_custom_query(self, query: str, *, allow_updates: bool = False) -> str:
        return self.client.run_custom_query(query, allow_updates=allow_updates)

    def delete_all_triples(self) -> None:
        self.client.delete_all_triples()
