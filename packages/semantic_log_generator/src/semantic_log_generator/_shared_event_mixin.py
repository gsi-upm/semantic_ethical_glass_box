"""Shared-event resolution and linking behavior for semantic logger."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Sequence

from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, RDFS, XSD

from .namespaces import SCHEMA, SOSA
from .types import RDFTermLike, SharedEventPolicy, SharedEventRequest, SharedEventResolver


class SharedEventMixin:
    @staticmethod
    def _canonicalize_text(value: str | None) -> str:
        """Canonicalizes text ONLY for hashing/fingerprinting (never for storing)."""
        if value is None:
            return ""
        return re.sub(r"\s+", " ", value.strip().lower())

    @staticmethod
    def _bucket_datetime_seconds(observed_at: datetime, *, bucket_seconds: int) -> datetime:
        if bucket_seconds <= 0:
            raise ValueError("Parameter 'bucket_seconds' must be a positive integer.")
        utc_value = observed_at if observed_at.tzinfo is not None else observed_at.replace(tzinfo=timezone.utc)
        utc_value = utc_value.astimezone(timezone.utc)
        bucket_epoch = int(utc_value.timestamp()) // bucket_seconds * bucket_seconds
        return datetime.fromtimestamp(bucket_epoch, tz=timezone.utc)

    def _set_if_absent(self, *, subject: URIRef, predicate: URIRef, object_value: RDFTermLike) -> None:
        if any(True for _ in self.graph.objects(subject, predicate)):
            return
        self.graph.add((subject, predicate, self.resolve_term(object_value)))

    def _set_literal_if_absent(self, *, subject: URIRef, predicate: URIRef, object_value: Literal) -> None:
        if any(True for _ in self.graph.objects(subject, predicate)):
            return
        self.graph.add((subject, predicate, object_value))

    def _add_sosa_modality_observation(
        self,
        *,
        event_uri: URIRef,
        observed_at: datetime,
        modality: str,
        text: str | None,
    ) -> None:
        observation_source = "|".join(
            (
                observed_at.isoformat(),
                self._canonicalize_text(modality),
                text or "",
            )
        )
        observation_digest = hashlib.sha256(observation_source.encode("utf-8")).hexdigest()[:12]
        observation_uri = URIRef(f"{event_uri}#observation-{observation_digest}")
        procedure_uri = URIRef(f"{event_uri}#procedure-{self._slugify(modality)}")

        self.graph.add((observation_uri, RDF.type, SOSA.Observation))
        self.graph.add((observation_uri, SOSA.hasFeatureOfInterest, event_uri))
        self.graph.add((observation_uri, SOSA.resultTime, self._literal(observed_at)))
        self.graph.add((observation_uri, SOSA.usedProcedure, procedure_uri))

        self.graph.add((procedure_uri, RDF.type, SOSA.Procedure))
        self.graph.add((procedure_uri, RDFS.label, Literal(modality, lang=self.default_language)))

        if text is not None:
            self.graph.add((observation_uri, SOSA.hasSimpleResult, Literal(text, lang=self.default_language)))

    def _add_shared_event_metadata(
        self,
        *,
        event_uri: URIRef,
        observed_at: datetime,
        subject_uri: URIRef | None,
        text: str | None,
        modality: str | None,
        event_types: Sequence[RDFTermLike] | None,
        time_bucket_seconds: int,
        event_key: str | None = None,
    ) -> None:
        bucket_dt = self._bucket_datetime_seconds(observed_at, bucket_seconds=time_bucket_seconds)

        raw_text = text.strip() if isinstance(text, str) and text.strip() else None
        raw_modality = modality.strip() if isinstance(modality, str) and modality.strip() else None

        self.graph.add((event_uri, RDF.type, PROV.Entity))
        self.graph.add((event_uri, RDF.type, SCHEMA.Event))
        if event_key:
            self._set_literal_if_absent(
                subject=event_uri,
                predicate=SCHEMA.identifier,
                object_value=Literal(event_key),
            )
        self._set_literal_if_absent(
            subject=event_uri,
            predicate=PROV.generatedAtTime,
            object_value=self._literal(bucket_dt),
        )

        if subject_uri is not None:
            self._set_if_absent(
                subject=event_uri,
                predicate=SCHEMA.about,
                object_value=subject_uri,
            )
        if raw_text:
            # Store original text; do not canonicalize content.
            self._set_literal_if_absent(
                subject=event_uri,
                predicate=SCHEMA.description,
                object_value=Literal(raw_text, lang=self.default_language),
            )
        if raw_modality:
            self._add_sosa_modality_observation(
                event_uri=event_uri,
                observed_at=bucket_dt,
                modality=raw_modality,
                text=raw_text,
            )

        for event_type in self._iter_terms(event_types):
            self.graph.add((event_uri, RDF.type, event_type))

    def get_shared_event_uri(
        self,
        *,
        event_kind: str,
        observed_at: datetime,
        subject: RDFTermLike | None = None,
        text: str | None = None,
        modality: str | None = None,
        shared_event_namespace: str | None = None,
        event_types: Sequence[RDFTermLike] | None = None,
        event_id: str | None = None,
        time_bucket_seconds: int | None = None,
        resolver: SharedEventResolver | None = None,
        policy: SharedEventPolicy | None = None,
    ) -> URIRef:
        """Gets a shared-event URI via external resolver or deterministic local fallback."""
        effective_policy = policy if policy is not None else self.shared_event_policy
        effective_namespace = shared_event_namespace if shared_event_namespace is not None else effective_policy.namespace
        effective_bucket = time_bucket_seconds if time_bucket_seconds is not None else effective_policy.time_bucket_seconds

        event_types_tuple = tuple(event_types) if event_types is not None else ()
        resolver_request = SharedEventRequest(
            event_kind=event_kind,
            observed_at=observed_at,
            subject=subject,
            text=text,
            modality=modality,
            shared_event_namespace=effective_namespace,
            event_types=event_types_tuple,
            event_id=event_id,
            time_bucket_seconds=effective_bucket,
        )
        resolver_fn = resolver if resolver is not None else self.shared_event_resolver

        subject_uri = self.resolve_term(subject) if subject is not None else None
        if resolver_fn is not None:
            resolved_event = resolver_fn(resolver_request)
            if resolved_event is not None:
                event_uri = self.resolve_term(resolved_event)
                if effective_namespace:
                    shared_ns = Namespace(self._normalize_base_namespace(effective_namespace))
                    self.graph.bind("shared-event", shared_ns)
                self._add_shared_event_metadata(
                    event_uri=event_uri,
                    observed_at=observed_at,
                    subject_uri=subject_uri,
                    text=text,
                    modality=modality,
                    event_types=event_types_tuple,
                    time_bucket_seconds=effective_bucket,
                    event_key=self._slugify(event_id) if event_id else None,
                )
                return event_uri

        return self.resolve_shared_event(
            event_kind=event_kind,
            observed_at=observed_at,
            subject=subject_uri,
            text=text,
            modality=modality,
            shared_event_namespace=effective_namespace,
            event_types=event_types_tuple,
            event_id=event_id,
            time_bucket_seconds=effective_bucket,
        )

    def resolve_shared_event(
        self,
        *,
        event_kind: str,
        observed_at: datetime,
        subject: RDFTermLike | None = None,
        text: str | None = None,
        modality: str | None = None,
        shared_event_namespace: str | None = None,
        event_types: Sequence[RDFTermLike] | None = None,
        event_id: str | None = None,
        time_bucket_seconds: int = 1,
    ) -> URIRef:
        """Returns a canonical SharedEvent URI and registers it as an RDF node."""
        if not isinstance(event_kind, str) or not event_kind.strip():
            raise ValueError("Parameter 'event_kind' must be a non-empty string.")
        if not isinstance(observed_at, datetime):
            raise TypeError("Parameter 'observed_at' must be a datetime.")

        namespace_text = self._normalize_base_namespace(shared_event_namespace or self.DEFAULT_SHARED_EVENT_NAMESPACE)
        shared_ns = Namespace(namespace_text)

        subject_uri = self.resolve_term(subject) if subject is not None else None
        bucket_dt = self._bucket_datetime_seconds(observed_at, bucket_seconds=time_bucket_seconds)

        canonical_text = self._canonicalize_text(text)
        canonical_modality = self._canonicalize_text(modality)
        canonical_kind = self._canonicalize_text(event_kind)

        if event_id is None:
            fingerprint_source = "|".join(
                (
                    canonical_kind,
                    bucket_dt.isoformat(),
                    str(subject_uri) if subject_uri is not None else "",
                    canonical_modality,
                    canonical_text,
                )
            )
            digest = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:20]
            event_key = f"{self._slugify(event_kind)}_{digest}"
        else:
            event_key = self._slugify(event_id)

        event_uri = shared_ns[event_key]
        self.graph.bind("shared-event", shared_ns)
        self._add_shared_event_metadata(
            event_uri=event_uri,
            observed_at=bucket_dt,
            subject_uri=subject_uri,
            text=text,  # store original text
            modality=modality,
            event_types=event_types,
            time_bucket_seconds=time_bucket_seconds,
            event_key=event_key,
        )
        return event_uri

    def link_observation_to_shared_event(
        self,
        observation_entity: RDFTermLike,
        shared_event: RDFTermLike,
        *,
        confidence: float | None = None,
    ) -> None:
        """Links one local observation entity to a canonical shared event."""
        observation_uri = self.resolve_term(observation_entity)
        shared_event_uri = self.resolve_term(shared_event)
        self.graph.add((observation_uri, PROV.specializationOf, shared_event_uri))
        self.graph.add((shared_event_uri, RDF.type, PROV.Entity))
        self.graph.add((shared_event_uri, RDF.type, SCHEMA.Event))
        if confidence is not None:
            confidence_source = f"{observation_uri}|{shared_event_uri}|shared_event_confidence"
            confidence_digest = hashlib.sha256(confidence_source.encode("utf-8")).hexdigest()[:12]
            confidence_property = self.resource_uri("observation-property", f"shared_event_confidence_{confidence_digest}")
            self.graph.add((confidence_property, RDF.type, SCHEMA.PropertyValue))
            self.graph.add((confidence_property, SCHEMA.propertyID, Literal("shared_event_confidence")))
            self.graph.add((confidence_property, SCHEMA.value, Literal(float(confidence), datatype=XSD.float)))
            self.graph.add((observation_uri, SCHEMA.additionalProperty, confidence_property))

    def link_activity_to_shared_event(
        self,
        activity: RDFTermLike,
        shared_event: RDFTermLike,
    ) -> None:
        """Adds a contextual relation between an activity and a shared event."""
        activity_uri = self.resolve_term(activity)
        shared_event_uri = self.resolve_term(shared_event)
        self.graph.add((activity_uri, SCHEMA.about, shared_event_uri))
        self.graph.add((shared_event_uri, RDF.type, PROV.Entity))
        self.graph.add((shared_event_uri, RDF.type, SCHEMA.Event))
