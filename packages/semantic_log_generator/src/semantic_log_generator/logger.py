"""Semantic logger to generate SEGB-compliant RDF logs for robots.

Important operational note:
- This module does not read sensors, ROS topics, databases or the central KG by itself.
- It only converts facts already known by the robot software stack into RDF triples.
- The caller (your ROS nodes/orchestrator) is responsible for acquiring observations
  (ASR output, detection events, emotion scores, telemetry, etc.) and passing them here.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import FOAF, PROV, RDF, XSD

from ._activity_mixin import ActivityMixin
from ._entity_mixin import EntityMixin
from ._shared_event_mixin import SharedEventMixin
from .namespaces import DEFAULT_PREFIXES, ORO, SCHEMA, SEGB
from .types import RDFTermLike, SharedEventPolicy, SharedEventResolver


class SemanticSEGBLogger(SharedEventMixin, ActivityMixin, EntityMixin):
    
    """Facade that orchestrates semantic log components.

    Responsibilities are delegated to focused mixins:
    - SharedEventMixin: canonical shared-event resolution and linking.
    - ActivityMixin: activities, causal links, and ML metadata.
    - EntityMixin: observations, messages, emotions, and robot state snapshots.
    """

    DEFAULT_SHARED_EVENT_NAMESPACE = "https://gsi.upm.es/segb/shared-events/"

    def __init__(
        self,
        *,
        base_namespace: str,
        robot_id: str,
        robot_name: str | None = None,
        default_language: str = "en",
        graph: Graph | None = None,
        namespace_prefix: str = "robotlog",
        compact_resource_ids: bool = False,
        shared_event_policy: SharedEventPolicy | None = None,
        shared_event_resolver: SharedEventResolver | None = None,
        emit_prov_redundant: bool = True,
        strict_result_typing: bool = False,
    ) -> None:
        self.base_namespace = self._normalize_base_namespace(base_namespace)
        self.base = Namespace(self.base_namespace)
        self.default_language = default_language
        self.graph = graph if graph is not None else Graph()
        self.namespace_prefix = self._normalize_prefix_label(namespace_prefix)
        self.compact_resource_ids = bool(compact_resource_ids)

        # If True, emit redundant PROV triples in addition to SEGB subproperties.
        # This improves interoperability in deployments without OWL reasoning enabled.
        self.emit_prov_redundant = bool(emit_prov_redundant)
        # If True, do not add explicit prov:Activity when marking segb:Result resources.
        # Keep False by default for compatibility with current SEGB backend assumptions.
        self.strict_result_typing = bool(strict_result_typing)

        self.prefixes: dict[str, Namespace] = dict(DEFAULT_PREFIXES)
        # Do not drop prefixes arbitrarily; keep all defaults for interoperability.
        self.prefixes[self.namespace_prefix] = self.base
        for prefix, namespace in self.prefixes.items():
            self.graph.bind(prefix, namespace)

        self.robot_uri = self.resource_uri("robot", robot_id)
        self.shared_event_policy = shared_event_policy if shared_event_policy is not None else SharedEventPolicy()
        self.shared_event_resolver = shared_event_resolver
        self.register_robot(robot_name=robot_name)

    @staticmethod
    def _normalize_base_namespace(base_namespace: str) -> str:
        if not isinstance(base_namespace, str) or not base_namespace.strip():
            raise ValueError("Parameter 'base_namespace' must be a non-empty string.")
        ns = base_namespace.strip()
        if ns.endswith(("#", "/")):
            return ns
        return ns + "/"

    @staticmethod
    def _slugify(text: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", text.strip()).strip("_").lower()
        return slug or uuid.uuid4().hex

    @staticmethod
    def _normalize_prefix_label(prefix: str) -> str:
        if not isinstance(prefix, str) or not prefix.strip():
            raise ValueError("Parameter 'namespace_prefix' must be a non-empty string.")
        normalized = re.sub(r"[^A-Za-z0-9_]+", "_", prefix.strip()).strip("_").lower()
        if not normalized:
            raise ValueError("Parameter 'namespace_prefix' must include at least one alphanumeric character.")
        if normalized[0].isdigit():
            normalized = f"ns_{normalized}"
        return normalized

    def resolve_term(self, value: RDFTermLike) -> URIRef:
        """Resolves a URIRef, absolute URI string, prefix:name string, or local identifier."""
        if isinstance(value, URIRef):
            return value
        if not isinstance(value, str) or not value.strip():
            raise ValueError("RDF term must be a non-empty string or URIRef.")
        term = value.strip()
        if term.startswith(("http://", "https://")):
            return URIRef(term)
        if ":" in term:
            prefix, local = term.split(":", 1)
            namespace = self.prefixes.get(prefix)
            if namespace is None:
                raise ValueError(
                    f"Unknown namespace prefix '{prefix}'. "
                    f"Known prefixes: {', '.join(sorted(self.prefixes))}."
                )
            if not local:
                raise ValueError("Invalid prefixed name. Missing local part after ':'.")
            return namespace[local]
        return self.base[term]

    def resource_uri(self, kind: str, resource_id: str | None = None) -> URIRef:
        """Builds a URI inside the robot log namespace."""
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("Parameter 'kind' must be a non-empty string.")
        suffix = self._slugify(resource_id) if resource_id else uuid.uuid4().hex
        if self.compact_resource_ids:
            return self.base[f"{self._slugify(kind)}_{suffix}"]
        return self.base[f"{kind.strip()}/{suffix}"]

    def _literal(self, value: Any) -> Literal:
        if isinstance(value, Literal):
            return value
        if isinstance(value, datetime):
            dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)
            lexical = dt.replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"
            return Literal(lexical, datatype=XSD.dateTime)
        if isinstance(value, bool):
            return Literal(value, datatype=XSD.boolean)
        if isinstance(value, int):
            return Literal(value, datatype=XSD.long)
        if isinstance(value, float):
            return Literal(value, datatype=XSD.double)
        return Literal(str(value))

    def _iter_terms(self, values: Sequence[RDFTermLike] | None) -> Iterable[URIRef]:
        if values is None:
            return ()
        return (self.resolve_term(value) for value in values)

    @staticmethod
    def _as_percent(value: float) -> float:
        """Normalizes values to 0..100 when schema:unitCode is PERCENT."""
        v = float(value)
        if 0.0 <= v <= 1.0:
            return v * 100.0
        return v

    def _mark_as_segb_result(self, uri: URIRef) -> None:
        
        """Adds segb:Result typing aligned to an externally inconsistent SEGB TBox.

        NOTE (ontology inconsistency - external, cannot be changed here):
        - In segb.ttl, segb:Result is declared as rdfs:subClassOf prov:Activity,
          but it is also used in ranges intersecting prov:Entity (e.g., segb:producedEntityResult range
          is (prov:Entity AND segb:Result)).
        - By default (compatibility mode), we type results explicitly as BOTH:
            - prov:Entity (when the node is an entity-like artifact), AND
            - segb:Result, AND (redundantly) prov:Activity (because segb:Result ⊑ prov:Activity).
        - In strict mode (`strict_result_typing=True`), the logger does not emit the redundant
          explicit `prov:Activity` triple for `segb:Result` resources.
        """

        self.graph.add((uri, RDF.type, SEGB.Result))
        if not self.strict_result_typing:
            # Redundant but needed for interoperability without a reasoner, given segb:Result ⊑ prov:Activity
            self.graph.add((uri, RDF.type, PROV.Activity))

    def register_robot(
        self,
        *,
        robot_uri: RDFTermLike | None = None,
        robot_name: str | None = None,
        owner: RDFTermLike | None = None,
    ) -> URIRef:
        """Registers the robot agent in the local graph."""
        uri = self.resolve_term(robot_uri) if robot_uri is not None else self.robot_uri
        # Prefer prov:Agent for a physical robot. Software agents should be modeled separately.
        self.graph.add((uri, RDF.type, PROV.Agent))
        self.graph.add((uri, RDF.type, ORO.Robot))
        if robot_name:
            self.graph.add((uri, SCHEMA.name, Literal(robot_name, lang=self.default_language)))
        if owner:
            self.graph.add((uri, ORO.belongsTo, self.resolve_term(owner)))
        self.robot_uri = uri
        return uri

    def register_human(
        self,
        human_id: str,
        *,
        first_name: str | None = None,
        homepage: str | None = None,
    ) -> URIRef:
        """Registers a human actor often used as interaction subject."""
        human_uri = self.resource_uri("human", human_id)
        self.graph.add((human_uri, RDF.type, PROV.Person))
        self.graph.add((human_uri, RDF.type, FOAF.Person))
        self.graph.add((human_uri, RDF.type, ORO.Human))
        if first_name:
            self.graph.add((human_uri, FOAF.firstName, Literal(first_name, lang=self.default_language)))
        if homepage:
            self.graph.add((human_uri, FOAF.homepage, URIRef(homepage)))
        return human_uri

    def merge_turtle(self, ttl_content: str) -> None:
        """Merges existing turtle content into the logger graph."""
        if not isinstance(ttl_content, str) or not ttl_content.strip():
            raise ValueError("Parameter 'ttl_content' must be a non-empty string.")
        self.graph.parse(data=ttl_content, format="turtle")

    def serialize(self, *, format: str = "turtle") -> str:
        data = self.graph.serialize(format=format)
        return data.decode("utf-8") if isinstance(data, bytes) else data

    def publish(self, publisher: Any, *, user: str | None = None) -> dict[str, Any]:
        """
        Publishes the current graph through a publisher object.
        The publisher must expose publish_graph(graph, user=None).
        """
        return publisher.publish_graph(self.graph, user=user)
