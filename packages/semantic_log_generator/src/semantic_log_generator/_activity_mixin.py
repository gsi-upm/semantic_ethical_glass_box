"""Activity and ML logging behavior for semantic logger."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Mapping, Sequence

from rdflib import Literal, URIRef
from rdflib.namespace import PROV, RDF, RDFS

from .namespaces import MLS, SCHEMA, SEGB
from .types import ActivityKind, ModelUsage, RDFTermLike


class ActivityMixin:
    ACTIVITY_KIND_TYPES: Mapping[ActivityKind, tuple[RDFTermLike, ...]] = {
        ActivityKind.LISTENING: ("oro:ListeningEvent",),
        ActivityKind.DECISION: ("oro:DecisionMakingAction",),
        ActivityKind.RESPONSE: ("oro:ResponseAction",),
        ActivityKind.EMOTION_RECOGNITION: ("oro:EmotionRecognitionEvent",),
        ActivityKind.EMOTION_ANALYSIS: ("onyx:EmotionAnalysis",),
        ActivityKind.HUMAN_DETECTION: ("oro:DetectedHumanEvent",),
        ActivityKind.ML_RUN: ("mls:Run",),
    }

    def register_ml_model(
        self,
        model_id: str,
        *,
        label: str | None = None,
        version: str | None = None,
        provider: RDFTermLike | str | None = None,
        endpoint: str | None = None,
        comment: str | None = None,
        characteristics: Mapping[str, Any] | None = None,
    ) -> URIRef:
        """Registers a machine learning model with optional metadata.

        NOTE (ontology inconsistency - external, cannot be changed here):
        segb:producedEntityResult range expects (prov:Entity AND segb:Result),
        but segb:Result is declared as a subclass of prov:Activity in segb.ttl.
        We therefore type SEGB "results" redundantly as prov:Activity when needed.
        """
        model_uri = self.resource_uri("model", model_id)
        self.graph.add((model_uri, RDF.type, MLS.Model))
        self.graph.add((model_uri, RDF.type, PROV.Entity))
        self._mark_as_segb_result(model_uri)
        if label:
            self.graph.add((model_uri, RDFS.label, Literal(label, lang=self.default_language)))
        if version:
            self.graph.add((model_uri, SCHEMA.version, Literal(version)))
        self._link_model_provider(model_uri=model_uri, provider=provider)
        if endpoint:
            if endpoint.startswith(("http://", "https://")):
                self.graph.add((model_uri, SCHEMA.url, URIRef(endpoint)))
            else:
                self.graph.add((model_uri, SCHEMA.url, Literal(endpoint)))
        if comment:
            self.graph.add((model_uri, RDFS.comment, Literal(comment, lang=self.default_language)))

        for name, value in (characteristics or {}).items():
            characteristic_uri = self.resource_uri("model-characteristic", f"{model_id}_{name}")
            self.graph.add((characteristic_uri, RDF.type, MLS.ModelCharacteristic))
            self.graph.add((characteristic_uri, RDFS.label, Literal(name, lang="en")))
            self.graph.add((characteristic_uri, MLS.hasValue, self._literal(value)))
            self.graph.add((model_uri, MLS.hasQuality, characteristic_uri))
        return model_uri

    def _link_model_provider(
        self,
        *,
        model_uri: URIRef,
        provider: RDFTermLike | str | None,
    ) -> None:
        if provider is None:
            return
        if isinstance(provider, URIRef):
            self.graph.add((model_uri, SCHEMA.provider, provider))
            return
        provider_text = str(provider).strip()
        if not provider_text:
            return
        if provider_text.startswith(("http://", "https://")):
            self.graph.add((model_uri, SCHEMA.provider, URIRef(provider_text)))
            return

        # For plain text providers, materialize an Organization node instead of a literal.
        provider_uri = self.resource_uri("organization", provider_text)
        self.graph.add((provider_uri, RDF.type, SCHEMA.Organization))
        self.graph.add((provider_uri, SCHEMA.name, Literal(provider_text, lang=self.default_language)))
        self.graph.add((model_uri, SCHEMA.provider, provider_uri))

    def _ensure_activity(self, activity_uri: URIRef, activity_types: Sequence[RDFTermLike] | None = None) -> None:
        # Redundant prov:Activity typing for interoperability without OWL reasoning.
        self.graph.add((activity_uri, RDF.type, PROV.Activity))
        self.graph.add((activity_uri, RDF.type, SEGB.LoggedActivity))
        for activity_type in self._iter_terms(activity_types):
            self.graph.add((activity_uri, RDF.type, activity_type))

    def _coerce_activity_kind(self, value: ActivityKind | str | None) -> ActivityKind | None:
        if value is None:
            return None
        if isinstance(value, ActivityKind):
            return value
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Parameter 'activity_kind' must be a non-empty string, ActivityKind, or None.")

        normalized = value.strip().lower().replace("-", "_")
        for member in ActivityKind:
            if normalized == member.value:
                return member
            if normalized == member.name.lower():
                return member
        allowed = ", ".join(kind.value for kind in ActivityKind)
        raise ValueError(f"Unknown activity kind '{value}'. Allowed values: {allowed}.")

    def _merge_activity_types(
        self,
        *,
        activity_kind: ActivityKind | str,
        extra_types: Sequence[RDFTermLike] | None,
    ) -> tuple[URIRef, ...]:
        kind = self._coerce_activity_kind(activity_kind)
        if kind is None:
            allowed = ", ".join(item.value for item in ActivityKind)
            raise ValueError(f"Parameter 'activity_kind' is required. Allowed values: {allowed}.")

        merged: list[RDFTermLike] = []
        merged.extend(self.ACTIVITY_KIND_TYPES[kind])
        if extra_types is not None:
            merged.extend(extra_types)

        deduplicated: list[URIRef] = []
        seen: set[URIRef] = set()
        for activity_type in merged:
            resolved = self.resolve_term(activity_type)
            if resolved in seen:
                continue
            seen.add(resolved)
            deduplicated.append(resolved)
        return tuple(deduplicated)

    def _link_model_usage(self, activity_uri: URIRef, usage: ModelUsage) -> None:
        model_uri = self.resolve_term(usage.model)
        self.graph.add((model_uri, RDF.type, MLS.Model))
        self.graph.add((activity_uri, SEGB.usedMLModel, model_uri))
        if self.emit_prov_redundant:
            # segb:usedMLModel is a subPropertyOf prov:used in segb.ttl, but emit redundantly for stores without reasoning.
            self.graph.add((activity_uri, PROV.used, model_uri))

        implementation_uri: URIRef | None = None
        requires_implementation = usage.implementation is not None or bool(usage.parameters) or bool(
            usage.software_label or usage.software_version
        )
        if requires_implementation:
            implementation_uri = (
                self.resolve_term(usage.implementation)
                if usage.implementation is not None
                else self.resource_uri("implementation")
            )
            self.graph.add((implementation_uri, RDF.type, MLS.Implementation))
            self.graph.add((implementation_uri, MLS.implements, model_uri))
            self.graph.add((activity_uri, MLS.executes, implementation_uri))

        if usage.software_label or usage.software_version:
            software_uri = self.resource_uri("software", usage.software_label)
            self.graph.add((software_uri, RDF.type, MLS.Software))
            if usage.software_label:
                self.graph.add((software_uri, RDFS.label, Literal(usage.software_label)))
            if usage.software_version:
                self.graph.add((software_uri, SCHEMA.version, Literal(usage.software_version)))
            if implementation_uri is not None:
                self.graph.add((software_uri, MLS.hasPart, implementation_uri))

        for key, value in usage.parameters.items():
            hyperparameter_uri = self.resource_uri("hyperparameter", key)
            setting_uri = self.resource_uri("hyperparameter-setting")

            self.graph.add((hyperparameter_uri, RDF.type, MLS.HyperParameter))
            self.graph.add((hyperparameter_uri, RDFS.label, Literal(str(key), lang="en")))

            self.graph.add((setting_uri, RDF.type, MLS.HyperParameterSetting))
            self.graph.add((setting_uri, MLS.specifiedBy, hyperparameter_uri))
            self.graph.add((setting_uri, MLS.hasValue, self._literal(value)))

            self.graph.add((activity_uri, MLS.hasInput, setting_uri))
            self.graph.add((activity_uri, PROV.used, setting_uri))
            if implementation_uri is not None:
                self.graph.add((implementation_uri, MLS.hasHyperParameter, hyperparameter_uri))

    def _link_activity_actor_and_time(
        self,
        *,
        activity_uri: URIRef,
        performer: RDFTermLike | None,
        started_at: datetime | None,
        ended_at: datetime | None,
    ) -> None:
        performer_uri = self.resolve_term(performer) if performer else self.robot_uri
        self.graph.add((activity_uri, SEGB.wasPerformedBy, performer_uri))
        if self.emit_prov_redundant:
            self.graph.add((activity_uri, PROV.wasAssociatedWith, performer_uri))
        if started_at:
            self._add_activity_time_if_consistent(
                activity_uri=activity_uri,
                predicate=PROV.startedAtTime,
                when=started_at,
                parameter_name="started_at",
            )
        if ended_at:
            self._add_activity_time_if_consistent(
                activity_uri=activity_uri,
                predicate=PROV.endedAtTime,
                when=ended_at,
                parameter_name="ended_at",
            )

    def _add_activity_time_if_consistent(
        self,
        *,
        activity_uri: URIRef,
        predicate: URIRef,
        when: datetime,
        parameter_name: str,
    ) -> None:
        literal = self._literal(when)
        existing_values = set(self.graph.objects(activity_uri, predicate))
        if not existing_values:
            self.graph.add((activity_uri, predicate, literal))
            return
        if literal in existing_values:
            return
        raise ValueError(
            f"Activity '{activity_uri}' already has a different value for '{parameter_name}'. "
            "Reuse the same activity_id only when referring to the same execution."
        )

    def _link_activity_shared_events(
        self,
        *,
        activity_uri: URIRef,
        related_shared_events: Sequence[RDFTermLike] | None,
    ) -> None:
        for shared_event_uri in self._iter_terms(related_shared_events):
            self.graph.add((activity_uri, SCHEMA.about, shared_event_uri))
            self.graph.add((shared_event_uri, RDF.type, PROV.Entity))
            self.graph.add((shared_event_uri, RDF.type, SCHEMA.Event))

    def _link_activity_triggers(
        self,
        *,
        activity_uri: URIRef,
        triggered_by_activity: RDFTermLike | None,
        triggered_by_entity: RDFTermLike | None,
        triggered_by_entities: Sequence[RDFTermLike] | None,
        intermediate_activities: Sequence[RDFTermLike] | None,
    ) -> None:
        if triggered_by_activity is not None:
            trigger_uri = self.resolve_term(triggered_by_activity)
            self.graph.add((activity_uri, SEGB.triggeredByActivity, trigger_uri))
            if self.emit_prov_redundant:
                self.graph.add((activity_uri, PROV.wasInfluencedBy, trigger_uri))

        entity_triggers: list[URIRef] = []
        if triggered_by_entity is not None:
            entity_triggers.append(self.resolve_term(triggered_by_entity))
        entity_triggers.extend(self._iter_terms(triggered_by_entities))
        for trigger_uri in entity_triggers:
            self.graph.add((activity_uri, SEGB.triggeredByEntity, trigger_uri))
            if self.emit_prov_redundant:
                self.graph.add((activity_uri, PROV.wasInfluencedBy, trigger_uri))

        for intermediate_uri in self._iter_terms(intermediate_activities):
            self.graph.add((activity_uri, SEGB.intermediateActivity, intermediate_uri))
            if self.emit_prov_redundant:
                self.graph.add((activity_uri, PROV.wasInfluencedBy, intermediate_uri))

    def _link_activity_inputs(
        self,
        *,
        activity_uri: URIRef,
        used_entities: Sequence[RDFTermLike] | None,
        used_models: Sequence[RDFTermLike] | None,
        model_usages: Sequence[ModelUsage] | None,
    ) -> None:
        for entity_uri in self._iter_terms(used_entities):
            self.graph.add((activity_uri, PROV.used, entity_uri))

        for model_uri in self._iter_terms(used_models):
            self.graph.add((activity_uri, SEGB.usedMLModel, model_uri))
            self.graph.add((model_uri, RDF.type, MLS.Model))
            if self.emit_prov_redundant:
                self.graph.add((activity_uri, PROV.used, model_uri))

        for usage in model_usages or ():
            self._link_model_usage(activity_uri, usage)

    def _link_activity_outputs(
        self,
        *,
        activity_uri: URIRef,
        produced_entity_results: Sequence[RDFTermLike] | None,
        produced_activity_results: Sequence[RDFTermLike] | None,
    ) -> None:
        for result_uri in self._iter_terms(produced_entity_results):
            self.graph.add((activity_uri, SEGB.producedEntityResult, result_uri))
            if self.emit_prov_redundant:
                self.graph.add((activity_uri, PROV.generated, result_uri))

        for result_uri in self._iter_terms(produced_activity_results):
            self.graph.add((activity_uri, SEGB.producedActivityResult, result_uri))

    def log_activity(
        self,
        *,
        activity_id: str | None = None,
        activity_kind: ActivityKind | str,
        extra_types: Sequence[RDFTermLike] | None = None,
        label: str | None = None,
        related_shared_events: Sequence[RDFTermLike] | None = None,
        performer: RDFTermLike | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        triggered_by_activity: RDFTermLike | None = None,
        triggered_by_entity: RDFTermLike | None = None,
        triggered_by_entities: Sequence[RDFTermLike] | None = None,
        intermediate_activities: Sequence[RDFTermLike] | None = None,
        used_entities: Sequence[RDFTermLike] | None = None,
        used_models: Sequence[RDFTermLike] | None = None,
        model_usages: Sequence[ModelUsage] | None = None,
        produced_entity_results: Sequence[RDFTermLike] | None = None,
        produced_activity_results: Sequence[RDFTermLike] | None = None,
    ) -> URIRef:
        """Logs one activity and its semantic relations.

        NOTE (ontology semantics):
        - segb:wasPerformedBy ⊑ prov:wasAssociatedWith
        - segb:triggeredBy* ⊑ prov:wasInfluencedBy
        - segb:producedEntityResult ⊑ prov:generated
        This logger can emit redundant PROV triples for deployments without OWL reasoning.
        """
        activity_uri = self.resource_uri("activity", activity_id)
        resolved_activity_types = self._merge_activity_types(
            activity_kind=activity_kind,
            extra_types=extra_types,
        )
        self._ensure_activity(activity_uri, resolved_activity_types)

        if label:
            self.graph.add((activity_uri, RDFS.label, Literal(label, lang=self.default_language)))

        self._link_activity_actor_and_time(
            activity_uri=activity_uri,
            performer=performer,
            started_at=started_at,
            ended_at=ended_at,
        )
        self._link_activity_shared_events(
            activity_uri=activity_uri,
            related_shared_events=related_shared_events,
        )
        self._link_activity_triggers(
            activity_uri=activity_uri,
            triggered_by_activity=triggered_by_activity,
            triggered_by_entity=triggered_by_entity,
            triggered_by_entities=triggered_by_entities,
            intermediate_activities=intermediate_activities,
        )
        self._link_activity_inputs(
            activity_uri=activity_uri,
            used_entities=used_entities,
            used_models=used_models,
            model_usages=model_usages,
        )
        self._link_activity_outputs(
            activity_uri=activity_uri,
            produced_entity_results=produced_entity_results,
            produced_activity_results=produced_activity_results,
        )

        return activity_uri

    def link_triggered_activity(
        self,
        activity: RDFTermLike,
        trigger_activity: RDFTermLike,
    ) -> None:
        """Adds a causal link where one activity is triggered by another activity."""
        activity_uri = self.resolve_term(activity)
        trigger_uri = self.resolve_term(trigger_activity)
        self.graph.add((activity_uri, SEGB.triggeredByActivity, trigger_uri))
        if self.emit_prov_redundant:
            self.graph.add((activity_uri, PROV.wasInfluencedBy, trigger_uri))

    def link_triggered_entity(
        self,
        activity: RDFTermLike,
        trigger_entity: RDFTermLike,
    ) -> None:
        """Adds a causal link where an entity triggers an activity."""
        activity_uri = self.resolve_term(activity)
        trigger_uri = self.resolve_term(trigger_entity)
        self.graph.add((activity_uri, SEGB.triggeredByEntity, trigger_uri))
        if self.emit_prov_redundant:
            self.graph.add((activity_uri, PROV.wasInfluencedBy, trigger_uri))

    def link_intermediate_activity(
        self,
        activity: RDFTermLike,
        intermediate_activity: RDFTermLike,
    ) -> None:
        """Links an activity to one of its intermediate steps."""
        activity_uri = self.resolve_term(activity)
        intermediate_uri = self.resolve_term(intermediate_activity)
        self.graph.add((activity_uri, SEGB.intermediateActivity, intermediate_uri))
        if self.emit_prov_redundant:
            self.graph.add((activity_uri, PROV.wasInfluencedBy, intermediate_uri))

    def link_influence(
        self,
        activity: RDFTermLike,
        influencer: RDFTermLike,
    ) -> None:
        """Adds an explicit prov:wasInfluencedBy relation."""
        self.graph.add((self.resolve_term(activity), PROV.wasInfluencedBy, self.resolve_term(influencer)))

    def link_entity_result(
        self,
        activity: RDFTermLike,
        entity_result: RDFTermLike,
    ) -> None:
        """Links an activity with an entity result and prov:generated."""
        activity_uri = self.resolve_term(activity)
        entity_uri = self.resolve_term(entity_result)
        self.graph.add((activity_uri, SEGB.producedEntityResult, entity_uri))
        if self.emit_prov_redundant:
            self.graph.add((activity_uri, PROV.generated, entity_uri))

    def link_activity_model(
        self,
        activity: RDFTermLike,
        model: RDFTermLike,
    ) -> None:
        """Links one activity to one ML model used during execution."""
        activity_uri = self.resolve_term(activity)
        model_uri = self.resolve_term(model)
        self.graph.add((activity_uri, SEGB.usedMLModel, model_uri))
        self.graph.add((model_uri, RDF.type, MLS.Model))
        if self.emit_prov_redundant:
            self.graph.add((activity_uri, PROV.used, model_uri))

    def register_dataset(
        self,
        dataset_id: str,
        *,
        label: str | None = None,
        comment: str | None = None,
    ) -> URIRef:
        """Registers an MLS dataset entity."""
        dataset_uri = self.resource_uri("dataset", dataset_id)
        self.graph.add((dataset_uri, RDF.type, MLS.Dataset))
        self.graph.add((dataset_uri, RDF.type, PROV.Entity))
        if label:
            self.graph.add((dataset_uri, RDFS.label, Literal(label, lang=self.default_language)))
        if comment:
            self.graph.add((dataset_uri, RDFS.comment, Literal(comment, lang=self.default_language)))
        return dataset_uri

    def register_model_evaluation(
        self,
        evaluation_id: str,
        *,
        value: float,
        label: str | None = None,
        comment: str | None = None,
    ) -> URIRef:
        """Registers an MLS model-evaluation entity with one score value."""
        evaluation_uri = self.resource_uri("model-eval", evaluation_id)
        self.graph.add((evaluation_uri, RDF.type, MLS.ModelEvaluation))
        self.graph.add((evaluation_uri, RDF.type, PROV.Entity))
        self.graph.add((evaluation_uri, MLS.hasValue, self._literal(float(value))))
        if label:
            self.graph.add((evaluation_uri, RDFS.label, Literal(label, lang=self.default_language)))
        if comment:
            self.graph.add((evaluation_uri, RDFS.comment, Literal(comment, lang=self.default_language)))
        return evaluation_uri

    def link_ml_run_input(
        self,
        run_activity: RDFTermLike,
        input_entity: RDFTermLike,
    ) -> None:
        """Links one MLS run activity to one input entity."""
        run_uri = self.resolve_term(run_activity)
        input_uri = self.resolve_term(input_entity)
        self.graph.add((run_uri, MLS.hasInput, input_uri))
        self.graph.add((run_uri, PROV.used, input_uri))

    def link_ml_run_output(
        self,
        run_activity: RDFTermLike,
        output_entity: RDFTermLike,
    ) -> None:
        """Links one MLS run activity to one output entity."""
        run_uri = self.resolve_term(run_activity)
        output_uri = self.resolve_term(output_entity)
        self.graph.add((run_uri, MLS.hasOutput, output_uri))
        self.graph.add((run_uri, PROV.generated, output_uri))
        self.graph.add((run_uri, SEGB.producedEntityResult, output_uri))
