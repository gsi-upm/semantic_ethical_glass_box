"""Virtuoso adapter used by application services."""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from pyparsing.exceptions import ParseBaseException
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF
from rdflib.plugins.sparql.parser import parseQuery, parseUpdate
from requests.auth import HTTPDigestAuth

from utils.audit import (
    AUDIT,
    AuditContext,
    build_deletion_entry,
    build_insertion_entry,
    entries_from_rows,
)
from utils.query_scope import QueryScopeError, check_read_query_scope
from utils.prefix_utils import (
    clean_prefixes_with_numbers,
    extract_prefixes,
    load_prefixes,
    save_prefixes,
)


class VirtuosoModel:
    """Thread-safe singleton wrapper around Virtuoso HTTP API."""

    _instance: "VirtuosoModel | None" = None
    _session: requests.Session | None = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        self.session = VirtuosoModel._session
        self.endpoint = os.getenv("VIRTUOSO_ENDPOINT", "http://segb-virtuoso:8890/sparql-auth")
        self.graph_uri = os.getenv("VIRTUOSO_GRAPH_URI", "http://segb/events")
        self.audit_graph_uri = os.getenv("VIRTUOSO_AUDIT_GRAPH_URI", "http://segb/audit")
        self.audit_base_iri = os.getenv("AUDIT_BASE_IRI", "http://segb/audit/")
        self.audit_dump_dir = Path(os.getenv("AUDIT_DUMP_DIR", "/data/audit-dumps"))
        self.audit_inline_ttl_max_bytes = int(os.getenv("AUDIT_INLINE_TTL_MAX_BYTES", str(4 * 1024 * 1024)))
        self.user = os.getenv("VIRTUOSO_USER", "dba")
        self.password = os.getenv("VIRTUOSO_PASSWORD") or os.getenv("DBA_PASSWORD")

    @classmethod
    def get_instance(cls) -> "VirtuosoModel":
        return cls()

    @classmethod
    def get_session(cls) -> requests.Session:
        if cls._session is None:
            raise RuntimeError("Virtuoso session is not initialized.")
        return cls._session

    def connect_to_db(self, retries: int = 10, delay: float = 5.0) -> requests.Session:
        if not self.password:
            raise RuntimeError("VIRTUOSO_PASSWORD (or DBA_PASSWORD) must be set.")
        with VirtuosoModel._lock:
            if VirtuosoModel._session is not None:
                self.session = VirtuosoModel._session
                return self.session

            session = requests.Session()
            session.auth = HTTPDigestAuth(self.user, self.password)
            session.headers.update({"Accept": "application/sparql-results+json"})

            last_error: Exception | None = None
            for _ in range(retries):
                try:
                    response = session.get(
                        self.endpoint,
                        params={"query": "ASK { ?s ?p ?o }", "timeout": 10000},
                        timeout=15,
                    )
                    if response.status_code == 200:
                        VirtuosoModel._session = session
                        self.session = session
                        return session
                    last_error = RuntimeError(f"HTTP {response.status_code}: {response.text[:120]}")
                except requests.RequestException as error:  # pragma: no cover - depends on external DB
                    last_error = error
                time.sleep(delay)

        raise ConnectionError(f"Could not connect to Virtuoso endpoint '{self.endpoint}'.") from last_error

    def close_connection(self) -> None:
        with VirtuosoModel._lock:
            if VirtuosoModel._session:
                VirtuosoModel._session.close()
            VirtuosoModel._session = None
            self.session = None

    def ping(self, timeout_s: float = 1.0) -> bool:
        try:
            response = self.get_session().get(
                self.endpoint,
                params={"query": "ASK {}", "format": "application/sparql-results+json"},
                headers={"Accept": "application/sparql-results+json"},
                timeout=timeout_s,
            )
            if response.status_code != 200:
                return False
            return bool(response.json().get("boolean") is True)
        except (requests.RequestException, RuntimeError, ValueError):
            return False

    def insert_ttl(self, ttl_content: str, *, audit: AuditContext) -> str:
        """Parses TTL once and inserts it into the events graph together with its audit entry.

        Both graphs are written by one SPARQL update, so a failed insert leaves no audit entry behind.
        """
        log_id = str(uuid.uuid4())
        graph = Graph()
        graph.parse(data=ttl_content, format="turtle")

        entry = build_insertion_entry(
            log_id=log_id,
            context=audit,
            ttl_content=ttl_content,
            base_iri=self.audit_base_iri,
            now=datetime.now(timezone.utc),
        )

        prefixes = extract_prefixes(ttl_content)
        save_prefixes(prefixes)

        for prefix, namespace_uri in load_prefixes().items():
            graph.bind(prefix, Namespace(namespace_uri))

        nt_data = graph.serialize(format="nt")
        if isinstance(nt_data, bytes):
            nt_data = nt_data.decode()
        audit_nt = entry.serialize(format="nt")
        if isinstance(audit_nt, bytes):
            audit_nt = audit_nt.decode()

        sparql_update = f"""
        INSERT DATA {{
          GRAPH <{self.graph_uri}> {{
            {nt_data}
          }}
          GRAPH <{self.audit_graph_uri}> {{
            {audit_nt}
          }}
        }}
        """

        response = self.get_session().post(
            self.endpoint,
            data=sparql_update.encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"},
            timeout=30,
        )
        response.raise_for_status()
        return log_id

    def _audit_select(self, query: str) -> list[dict[str, Any]]:
        response = self.get_session().get(
            self.endpoint,
            params={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["results"]["bindings"]

    def _audit_agent_names(self) -> dict[str, str]:
        rows = self._audit_select(
            f"SELECT ?a ?n FROM <{self.audit_graph_uri}> WHERE {{ ?a <http://xmlns.com/foaf/0.1/accountName> ?n }}"
        )
        return {row["a"]["value"]: row["n"]["value"] for row in rows}

    def list_audit_entries(self) -> list[dict[str, Any]]:
        """Summaries of every audit entry, oldest first. Reads only the audit graph and skips the TTL payloads."""
        rows = self._audit_select(
            f"""
            SELECT ?e ?p ?o FROM <{self.audit_graph_uri}>
            WHERE {{
              ?e a ?kind . FILTER(?kind IN (<{AUDIT.Insertion}>, <{AUDIT.Deletion}>))
              ?e ?p ?o .
              FILTER(?p NOT IN (<{AUDIT.ttl}>, <{AUDIT.mentionsSubject}>))
            }}
            """
        )
        flat = [{"e": r["e"]["value"], "p": r["p"]["value"], "o": r["o"]["value"]} for r in rows]
        return [view.summary for view in entries_from_rows(flat, self._audit_agent_names() if flat else {})]

    def get_audit_entry(self, log_id: str) -> dict[str, Any] | None:
        """One audit entry with its payload, or ``None`` when the id is not a UUID or is unknown.

        The id is interpolated into an IRI, so anything that is not a canonical UUID is rejected up front.
        """
        try:
            canonical = str(uuid.UUID(log_id))
        except (ValueError, AttributeError, TypeError):
            return None
        if canonical != log_id.lower():
            return None
        base = self.audit_base_iri if self.audit_base_iri.endswith("/") else f"{self.audit_base_iri}/"
        entry = f"{base}entry/{canonical}"
        rows = self._audit_select(f"SELECT ?p ?o FROM <{self.audit_graph_uri}> WHERE {{ <{entry}> ?p ?o }}")
        if not rows:
            return None
        flat = [{"e": entry, "p": r["p"]["value"], "o": r["o"]["value"]} for r in rows]
        views = entries_from_rows(flat, self._audit_agent_names())
        if not views:
            return None
        return {"log": views[0].summary, "action": views[0].action}

    def get_ttls(self) -> str:
        query = f"""
        CONSTRUCT {{ ?s ?p ?o . }}
        FROM <{self.graph_uri}>
        WHERE {{ ?s ?p ?o . }}
        """

        response = self.get_session().get(
            self.endpoint,
            params={"query": query, "format": "application/rdf+xml"},
            headers={"Accept": "application/rdf+xml"},
            timeout=30,
        )
        response.raise_for_status()

        graph = Graph()
        graph.parse(data=response.text, format="xml")

        for prefix, namespace_uri in load_prefixes().items():
            graph.bind(prefix, Namespace(namespace_uri))

        turtle_data = graph.serialize(format="turtle")
        if isinstance(turtle_data, bytes):
            turtle_data = turtle_data.decode()
        return clean_prefixes_with_numbers(turtle_data)

    def _leading_keyword(self, query: str) -> str:
        text = query.strip()
        while True:
            text = re.sub(r"^\s*#.*(?:\n|$)", "", text)
            directive = re.match(r"^\s*(?:PREFIX|BASE)\b[^\n]*(?:\n|$)", text, flags=re.IGNORECASE)
            if not directive:
                break
            text = text[directive.end() :]

        match = re.match(r"^\s*([A-Z]+)\b", text, flags=re.IGNORECASE)
        return (match.group(1).upper() if match else "").strip()

    def _query_kind(self, query: str) -> str:
        keyword = self._leading_keyword(query)
        if keyword in {"SELECT", "CONSTRUCT", "ASK", "DESCRIBE"}:
            return keyword.lower()
        if keyword in {"INSERT", "DELETE", "LOAD", "CLEAR", "DROP", "CREATE", "COPY", "MOVE", "ADD"}:
            return "update"
        return "unknown"

    def _update_uses_graph_clause(self, query: str) -> bool:
        return bool(re.search(r"(?i)\bGRAPH\b", query))

    def _prepare_update_query(self, query: str) -> str:
        if self._update_uses_graph_clause(query):
            return query
        return f"DEFINE input:default-graph-uri <{self.graph_uri}>\n{query}"

    def validate_query(self, query: str, *, allow_updates: bool = False) -> dict[str, Any]:
        kind = self._query_kind(query)
        if kind == "unknown":
            return {
                "valid": False,
                "query_kind": kind,
                "allows_update_execution": allow_updates,
                "message": "Query must start with SELECT/CONSTRUCT/ASK/DESCRIBE or an update operation.",
            }

        if kind == "update":
            if not allow_updates:
                return {
                    "valid": False,
                    "query_kind": kind,
                    "allows_update_execution": allow_updates,
                    "message": "Update queries are not allowed for this request.",
                }
            try:
                parseUpdate(query)
            except (ParseBaseException, ValueError) as error:
                return {
                    "valid": False,
                    "query_kind": kind,
                    "allows_update_execution": allow_updates,
                    "message": f"Invalid SPARQL update syntax: {str(error).strip() or 'Invalid syntax.'}",
                }
            return {
                "valid": True,
                "query_kind": kind,
                "allows_update_execution": allow_updates,
                "message": (
                    "Valid SPARQL update query."
                    if self._update_uses_graph_clause(query)
                    else f"Valid SPARQL update query. It will use default graph <{self.graph_uri}>."
                ),
            }

        try:
            parseQuery(query)
        except (ParseBaseException, ValueError) as error:
            return {
                "valid": False,
                "query_kind": kind,
                "allows_update_execution": allow_updates,
                "message": f"Invalid SPARQL syntax: {str(error).strip() or 'Invalid syntax.'}",
            }

        try:
            check_read_query_scope(query, self.graph_uri)
        except QueryScopeError as error:
            return {
                "valid": False,
                "query_kind": kind,
                "allows_update_execution": allow_updates,
                "message": str(error),
            }

        return {
            "valid": True,
            "query_kind": kind,
            "allows_update_execution": allow_updates,
            "message": "Valid SPARQL query.",
        }

    def run_custom_query(self, query: str, *, allow_updates: bool = False) -> str:
        validation = self.validate_query(query, allow_updates=allow_updates)
        if not bool(validation.get("valid")):
            message = str(validation.get("message") or "Invalid SPARQL query.")
            kind = str(validation.get("query_kind") or "unknown")
            if kind == "update":
                raise PermissionError(message)
            raise ValueError(message)

        kind = str(validation["query_kind"])
        if kind == "update":
            update_query = self._prepare_update_query(query)
            response = self.get_session().post(
                self.endpoint,
                data=update_query.encode("utf-8"),
                headers={"Content-Type": "application/sparql-update"},
                timeout=60,
            )
            try:
                response.raise_for_status()
            except requests.HTTPError as error:
                response_text = (response.text or "").strip()
                detail = response_text[:400] if response_text else str(error)
                raise ValueError(f"SPARQL update rejected: {detail}") from error
            if self._update_uses_graph_clause(query):
                return "SPARQL update executed successfully."
            return f"SPARQL update executed successfully on default graph <{self.graph_uri}>."

        is_construct = kind == "construct"
        accept_header = "text/turtle" if is_construct else "application/sparql-results+json"

        response = self.get_session().get(
            self.endpoint,
            params={
                "query": query,
                "format": accept_header,
                # Pin the dataset to the events graph. Without it Virtuoso queries the union of all graphs,
                # audit included; named-graph-uri also confines GRAPH ?g.
                "default-graph-uri": self.graph_uri,
                "named-graph-uri": self.graph_uri,
            },
            headers={"Accept": accept_header},
            timeout=60,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            response_text = (response.text or "").strip()
            detail = response_text[:400] if response_text else str(error)
            raise ValueError(f"SPARQL query rejected: {detail}") from error

        graph = Graph()

        def parse_binding_term(binding_value: dict[str, Any]):
            value_type = binding_value.get("type")
            value = binding_value.get("value")
            if value_type == "uri":
                return URIRef(value)
            if value_type == "literal":
                return Literal(value, lang=binding_value.get("xml:lang"), datatype=binding_value.get("datatype"))
            if value_type == "bnode":
                return BNode(value)
            return Literal(value)

        if is_construct:
            graph.parse(data=response.text, format="turtle")
        else:
            data_json = response.json()
            rows = data_json.get("results", {}).get("bindings", [])
            variables = data_json.get("head", {}).get("vars", [])
            for row in rows:
                result_ns = Namespace("http://example.org/")
                node = BNode()
                graph.add((node, RDF.type, result_ns.Result))
                for var in variables:
                    if var in row:
                        graph.add((node, result_ns[var], parse_binding_term(row[var])))

        for prefix, namespace_uri in load_prefixes().items():
            graph.bind(prefix, Namespace(namespace_uri))

        turtle_result = graph.serialize(format="turtle", encoding="utf-8")
        if isinstance(turtle_result, bytes):
            turtle_result = turtle_result.decode()
        return clean_prefixes_with_numbers(turtle_result)

    def delete_all_triples(self, *, audit: AuditContext) -> str | None:
        """Clears the events graph after storing its full dump in a deletion audit entry.

        The entry and the ``CLEAR`` go in one SPARQL update, so a failed clear leaves no entry. The audit graph is
        never cleared. Returns the entry id, or ``None`` when the graph was already empty (nothing to record).
        """
        ttl_text = self.get_ttls()
        if not ttl_text.strip():
            return None

        log_id = str(uuid.uuid4())
        dump_bytes = ttl_text.encode("utf-8")
        dump_file: Path | None = None
        if len(dump_bytes) <= self.audit_inline_ttl_max_bytes:
            file_fields: dict[str, Any] = {"ttl_content": ttl_text}
        else:
            # Virtuoso rejects SPARQL statements of about 10 MB, so a large dump cannot travel inside the entry.
            dump_file = self._write_dump_file(log_id, dump_bytes)
            file_fields = {
                "ttl_content": None,
                "ttl_file": dump_file.name,
                "ttl_sha256": hashlib.sha256(dump_bytes).hexdigest(),
            }

        entry = build_deletion_entry(
            log_id=log_id,
            context=audit,
            base_iri=self.audit_base_iri,
            now=datetime.now(timezone.utc),
            **file_fields,
        )
        audit_nt = entry.serialize(format="nt")
        if isinstance(audit_nt, bytes):
            audit_nt = audit_nt.decode()

        sparql_update = f"""
        INSERT DATA {{
          GRAPH <{self.audit_graph_uri}> {{
            {audit_nt}
          }}
        }} ;
        CLEAR GRAPH <{self.graph_uri}>
        """
        try:
            response = self.get_session().post(
                self.endpoint,
                data=sparql_update.encode("utf-8"),
                headers={"Content-Type": "application/sparql-update"},
                timeout=120,
            )
            response.raise_for_status()
        except BaseException:
            if dump_file is not None:
                dump_file.unlink(missing_ok=True)
            raise
        return log_id

    def _write_dump_file(self, log_id: str, content: bytes) -> Path:
        """Durably writes a dump to the audit dump directory; raises before anything is cleared if it cannot."""
        self.audit_dump_dir.mkdir(parents=True, exist_ok=True)
        target = self.audit_dump_dir / f"{log_id}.ttl"
        partial = target.with_suffix(".ttl.part")
        with open(partial, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        partial.replace(target)
        return target
