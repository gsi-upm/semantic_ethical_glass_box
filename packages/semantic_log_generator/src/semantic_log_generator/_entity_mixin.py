"""Entity/message/emotion/state logging behavior for semantic logger."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from rdflib import Literal, URIRef
from rdflib.namespace import PROV, RDF, RDFS, XSD

from .namespaces import AMOR, EMOML, OA, ONYX, ORO, SCHEMA, SEGB
from .types import EmotionCategory, EmotionScore, RDFTermLike, RobotStateSnapshot


class EntityMixin:
    def _resolve_emotion_category(self, category: EmotionCategory | RDFTermLike) -> URIRef:
        """Resolves strict big6 labels or explicit RDF terms for emotion category."""
        if isinstance(category, EmotionCategory):
            return self.resolve_term(category.value)
        if isinstance(category, URIRef):
            return category
        if not isinstance(category, str) or not category.strip():
            raise ValueError("Emotion category must be EmotionCategory, URIRef, or a non-empty RDF term string.")

        raw = category.strip()
        try:
            coerced = EmotionCategory.coerce(raw)
            return self.resolve_term(coerced.value)
        except ValueError:
            pass

        if raw.startswith(("http://", "https://")):
            return self.resolve_term(raw)

        if ":" in raw:
            prefix, local = raw.split(":", 1)
            if prefix == "emoml" and local.startswith("big6_"):
                allowed = {item.value.split(":", 1)[1] for item in EmotionCategory}
                if local not in allowed:
                    allowed_str = ", ".join(sorted(allowed))
                    raise ValueError(
                        f"Unknown EmotionML big6 category '{raw}'. Allowed values: {allowed_str}."
                    )
            return self.resolve_term(raw)

        allowed_values = ", ".join(item.value for item in EmotionCategory)
        raise ValueError(
            "Emotion category must be one of EmotionCategory values "
            f"({allowed_values}) or an explicit URI/prefixed term."
        )

    def log_observation(
        self,
        *,
        observation_id: str | None = None,
        label: str | None = None,
        observation_types: Sequence[RDFTermLike] | None = None,
        generated_by_activity: RDFTermLike | None = None,
        related_shared_event: RDFTermLike | None = None,
        confidence: float | None = None,
        mark_as_result: bool = False,
    ) -> URIRef:
        """Logs a generic observation entity and optional contextual links.

        NOTE (ontology inconsistency - external, cannot be changed here):
        If mark_as_result=True, we add segb:Result which (in segb.ttl) is a subclass of prov:Activity,
        while observations are also prov:Entity. This dual-typing is required to satisfy segb ranges.
        """
        if confidence is not None and related_shared_event is None:
            raise ValueError("Parameter 'confidence' requires 'related_shared_event'.")

        observation_uri = self.resource_uri("observation", observation_id)
        self.graph.add((observation_uri, RDF.type, PROV.Entity))
        if mark_as_result:
            self._mark_as_segb_result(observation_uri)
        for observation_type in self._iter_terms(observation_types):
            self.graph.add((observation_uri, RDF.type, observation_type))
        if label:
            self.graph.add((observation_uri, RDFS.label, Literal(label, lang=self.default_language)))

        if generated_by_activity is not None:
            activity_uri = self.resolve_term(generated_by_activity)
            # Ensure activity typing for interoperability even if caller didn't log it first.
            self._ensure_activity(activity_uri, None)
            self.graph.add((observation_uri, PROV.wasGeneratedBy, activity_uri))
            self.graph.add((activity_uri, SEGB.producedEntityResult, observation_uri))
            if self.emit_prov_redundant:
                self.graph.add((activity_uri, PROV.generated, observation_uri))

        if related_shared_event is not None:
            self.link_observation_to_shared_event(observation_uri, related_shared_event, confidence=confidence)

        return observation_uri

    def log_message(
        self,
        text: str,
        *,
        message_id: str | None = None,
        language: str | None = None,
        message_types: Sequence[RDFTermLike] | None = None,
        generated_by_activity: RDFTermLike | None = None,
        previous_message: RDFTermLike | None = None,
        sender: RDFTermLike | None = None,
    ) -> URIRef:
        """Logs a message entity, optional sender attribution, and conversational relations."""
        message_uri = self.resource_uri("message", message_id)
        self.graph.add((message_uri, RDF.type, SCHEMA.Message))
        self.graph.add((message_uri, RDF.type, PROV.Entity))

        resolved_types = {self.resolve_term(t) for t in (message_types or ())}
        for message_type in resolved_types:
            self.graph.add((message_uri, RDF.type, message_type))

        # Enforce explicit language for human input messages to avoid systematic @en mislabeling.
        if language is None and ORO.InitialMessage in resolved_types:
            raise ValueError(
                "Human input messages (oro:InitialMessage) require an explicit language tag (e.g., 'es', 'en')."
            )
        literal_language = language or self.default_language
        self.graph.add((message_uri, SCHEMA.text, Literal(text, lang=literal_language)))

        if sender is not None:
            sender_uri = self.resolve_term(sender)
            self.graph.add((message_uri, SCHEMA.sender, sender_uri))
            self.graph.add((message_uri, PROV.wasAttributedTo, sender_uri))

        if generated_by_activity:
            activity_uri = self.resolve_term(generated_by_activity)
            self._ensure_activity(activity_uri, None)
            self.graph.add((message_uri, PROV.wasGeneratedBy, activity_uri))
            self.graph.add((activity_uri, SEGB.producedEntityResult, message_uri))
            if self.emit_prov_redundant:
                self.graph.add((activity_uri, PROV.generated, message_uri))

        if previous_message:
            previous_uri = self.resolve_term(previous_message)
            self.graph.add((message_uri, PROV.wasDerivedFrom, previous_uri))
        return message_uri

    def log_emotion_annotation(
        self,
        *,
        source_activity: RDFTermLike,
        targets: Sequence[RDFTermLike],
        emotions: Sequence[EmotionScore],
        annotation_id: str | None = None,
        emotion_model: RDFTermLike = EMOML.big6,
    ) -> URIRef:
        """Logs emotion analysis results using ONYX and EmotionML categories.

        NOTE (ontology inconsistency - external, cannot be changed here):
        segb:producedEntityResult range expects (prov:Entity AND segb:Result),
        while segb:Result is a subclass of prov:Activity in segb.ttl.
        We therefore type the annotation as prov:Entity + segb:Result + (redundantly) prov:Activity.
        """
        if not emotions:
            raise ValueError("Parameter 'emotions' cannot be empty.")

        source_activity_uri = self.resolve_term(source_activity)
        self._ensure_activity(source_activity_uri, (ONYX.EmotionAnalysis,))
        self.graph.add((source_activity_uri, ONYX.usesEmotionModel, self.resolve_term(emotion_model)))

        annotation_uri = self.resource_uri("emotion-annotation", annotation_id)
        self.graph.add((annotation_uri, RDF.type, AMOR.EmotionAnnotation))
        self.graph.add((annotation_uri, RDF.type, OA.Annotation))
        self.graph.add((annotation_uri, RDF.type, PROV.Entity))
        self._mark_as_segb_result(annotation_uri)

        self.graph.add((source_activity_uri, SEGB.producedEntityResult, annotation_uri))
        if self.emit_prov_redundant:
            self.graph.add((source_activity_uri, PROV.generated, annotation_uri))

        # OA targets: allowed as a list, but be aware that multiple targets can be ambiguous semantically.
        for target in self._iter_terms(targets):
            self.graph.add((annotation_uri, OA.hasTarget, target))

        for emotion in emotions:
            emotion_uri = self.resource_uri("emotion")
            self.graph.add((emotion_uri, RDF.type, ONYX.Emotion))
            emotion_category_uri = self._resolve_emotion_category(emotion.category)
            self.graph.add((emotion_uri, ONYX.hasEmotionCategory, emotion_category_uri))
            self.graph.add((emotion_uri, ONYX.hasEmotionIntensity, Literal(float(emotion.intensity), datatype=XSD.float)))
            if emotion.confidence is not None:
                self.graph.add((emotion_uri, ONYX.algorithmConfidence, Literal(float(emotion.confidence), datatype=XSD.float)))
            self.graph.add((annotation_uri, ONYX.hasEmotion, emotion_uri))

        return annotation_uri

    def _add_state_property(
        self,
        *,
        state_uri: URIRef,
        property_id: str,
        value: Any,
        unit_code: str | None = None,
    ) -> URIRef:
        property_uri = self.resource_uri("state-property", f"{property_id}_{uuid.uuid4().hex}")
        self.graph.add((property_uri, RDF.type, SCHEMA.PropertyValue))
        self.graph.add((property_uri, SCHEMA.propertyID, Literal(property_id)))
        self.graph.add((property_uri, SCHEMA.value, self._literal(value)))
        if unit_code:
            self.graph.add((property_uri, SCHEMA.unitCode, Literal(unit_code)))
        self.graph.add((state_uri, SCHEMA.additionalProperty, property_uri))
        return property_uri

    def _link_state_source_activity(
        self,
        *,
        state_uri: URIRef,
        source_activity: RDFTermLike | None,
    ) -> None:
        if source_activity is None:
            return
        source_uri = self.resolve_term(source_activity)
        self._ensure_activity(source_uri, None)
        self.graph.add((source_uri, SEGB.producedEntityResult, state_uri))
        if self.emit_prov_redundant:
            self.graph.add((source_uri, PROV.generated, state_uri))

    def _link_state_location(self, *, state_uri: URIRef, location: RDFTermLike | None) -> None:
        if not location:
            return
        if isinstance(location, URIRef):
            self.graph.add((state_uri, PROV.atLocation, location))
            return
        if isinstance(location, str) and location.startswith(("http://", "https://")):
            self.graph.add((state_uri, PROV.atLocation, URIRef(location)))
            return
        self.graph.add((state_uri, PROV.atLocation, self.resolve_term(location)))

    def _link_state_properties(self, *, state_uri: URIRef, snapshot: RobotStateSnapshot) -> None:
        numeric_percent_values = (
            ("battery_level", snapshot.battery_level),
            ("cpu_load", snapshot.cpu_load),
            ("memory_load", snapshot.memory_load),
        )
        for property_id, value in numeric_percent_values:
            if value is None:
                continue
            self._add_state_property(
                state_uri=state_uri,
                property_id=property_id,
                value=self._as_percent(value),
                unit_code="PERCENT",
            )

        text_values = (
            ("autonomy_mode", snapshot.autonomy_mode),
            ("mission_phase", snapshot.mission_phase),
            ("network_status", snapshot.network_status),
        )
        for property_id, value in text_values:
            if value is None:
                continue
            self._add_state_property(
                state_uri=state_uri,
                property_id=property_id,
                value=value,
            )

        for custom_key, custom_value in snapshot.custom.items():
            self._add_state_property(
                state_uri=state_uri,
                property_id=str(custom_key),
                value=custom_value,
            )

    def log_robot_state(
        self,
        snapshot: RobotStateSnapshot,
        *,
        state_id: str | None = None,
        source_activity: RDFTermLike | None = None,
    ) -> URIRef:
        """
        Logs one robot state snapshot as an RDF entity.
        Snapshot values are represented with schema:PropertyValue nodes.

        NOTE (ontology inconsistency - external, cannot be changed here):
        If we type the state as segb:Result, segb.ttl implies it is also a prov:Activity.
        We keep state as prov:Entity and add segb:Result + prov:Activity redundantly
        to satisfy segb:producedEntityResult range constraints in stores without reasoning.
        """
        state_uri = self.resource_uri("state", state_id)
        self.graph.add((state_uri, RDF.type, PROV.Entity))
        self._mark_as_segb_result(state_uri)

        self.graph.add((state_uri, PROV.wasAttributedTo, self.robot_uri))
        self.graph.add((state_uri, PROV.generatedAtTime, self._literal(snapshot.timestamp or datetime.now(timezone.utc))))
        self._link_state_source_activity(state_uri=state_uri, source_activity=source_activity)
        self._link_state_location(state_uri=state_uri, location=snapshot.location)

        if snapshot.note:
            self.graph.add((state_uri, RDFS.comment, Literal(snapshot.note, lang=self.default_language)))
        self._link_state_properties(state_uri=state_uri, snapshot=snapshot)

        return state_uri
