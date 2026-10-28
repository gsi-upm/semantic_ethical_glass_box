import os
from datetime import datetime, timezone
import unittest

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF, RDFS, XSD

from semantic_log_generator import (
    ActivityKind,
    EmotionCategory,
    EmotionScore,
    ModelUsage,
    RobotStateSnapshot,
    SemanticSEGBLogger,
    SharedEventPolicy,
)
from semantic_log_generator.namespaces import AMOR, MLS, OA, ONYX, ORO, SCHEMA, SEGB, SOSA


class TestSemanticSEGBLogger(unittest.TestCase):
    def setUp(self) -> None:
        # Keep unit tests hermetic even if the developer environment exports SEGB_* vars.
        self._segb_env_keys = (
            "SEGB_API_URL",
            "SEGB_API_TOKEN",
            "SEGB_SHARED_CONTEXT_TIMEOUT_SECONDS",
            "SEGB_SHARED_CONTEXT_VERIFY_TLS",
            "SEGB_SHARED_CONTEXT_RAISE_ON_ERROR",
        )
        self._segb_env_backup = {key: os.environ.get(key) for key in self._segb_env_keys}
        for key in self._segb_env_keys:
            os.environ.pop(key, None)

        self.logger = SemanticSEGBLogger(
            base_namespace="http://example.org/segb/robots/ari1/",
            robot_id="ari1",
            robot_name="ARI",
        )

    def tearDown(self) -> None:
        for key in self._segb_env_keys:
            os.environ.pop(key, None)
        for key, value in self._segb_env_backup.items():
            if value is not None:
                os.environ[key] = value

    def test_activity_links_and_model_config(self) -> None:
        listening = self.logger.log_activity(
            activity_id="listen_1",
            activity_kind=ActivityKind.LISTENING,
            started_at=datetime.now(timezone.utc),
        )

        model = self.logger.register_ml_model("decision_model", label="Decision model")
        decision = self.logger.log_activity(
            activity_id="decision_1",
            activity_kind=ActivityKind.DECISION,
            triggered_by_activity=listening,
            model_usages=[
                ModelUsage(
                    model=model,
                    parameters={"temperature": 0.1, "max_tokens": 128},
                    software_label="llm-runtime",
                    software_version="1.2.3",
                )
            ],
        )

        graph = self.logger.graph
        self.assertIn((decision, SEGB.triggeredByActivity, listening), graph)
        self.assertIn((decision, SEGB.usedMLModel, model), graph)
        self.assertIn((decision, RDF.type, ORO.DecisionMakingAction), graph)

        settings = list(graph.objects(decision, MLS.hasInput))
        self.assertGreater(len(settings), 0)
        for setting in settings:
            self.assertIn((setting, RDF.type, MLS.HyperParameterSetting), graph)

    def test_register_ml_model_plain_text_provider_is_materialized_as_organization(self) -> None:
        model = self.logger.register_ml_model("provider_model_text", provider="OpenAI")
        graph = self.logger.graph

        providers = list(graph.objects(model, SCHEMA.provider))
        self.assertEqual(len(providers), 1)
        self.assertTrue(all(not isinstance(item, Literal) for item in providers))

        provider_uri = providers[0]
        self.assertIsInstance(provider_uri, URIRef)
        self.assertIn((provider_uri, RDF.type, SCHEMA.Organization), graph)
        self.assertIn((provider_uri, SCHEMA.name, Literal("OpenAI", lang=self.logger.default_language)), graph)

    def test_register_ml_model_uri_provider_is_kept_as_resource(self) -> None:
        provider_uri = URIRef("https://example.org/org/provider_acme")
        model = self.logger.register_ml_model("provider_model_uri", provider=provider_uri)
        graph = self.logger.graph

        providers = list(graph.objects(model, SCHEMA.provider))
        self.assertEqual(providers, [provider_uri])
        self.assertTrue(all(not isinstance(item, Literal) for item in providers))

    def test_register_robot_uses_schema_name(self) -> None:
        graph = self.logger.graph
        self.assertIn((self.logger.robot_uri, SCHEMA.name, Literal("ARI", lang=self.logger.default_language)), graph)
        self.assertEqual(len(list(graph.objects(self.logger.robot_uri, ORO.hasName))), 0)

    def test_log_message_uses_schema_message_and_text(self) -> None:
        message_uri = self.logger.log_message(
            "hola",
            message_id="schema_message_shape",
            language="es",
        )
        graph = self.logger.graph
        self.assertIn((message_uri, RDF.type, SCHEMA.Message), graph)
        self.assertIn((message_uri, SCHEMA.text, Literal("hola", lang="es")), graph)
        self.assertEqual(len(list(graph.objects(message_uri, ORO.hasText))), 0)

    def test_log_message_can_set_sender_and_attribution(self) -> None:
        human = self.logger.register_human("maria_sender", first_name="Maria")
        listening = self.logger.log_activity(
            activity_id="listening_sender",
            activity_kind=ActivityKind.LISTENING,
            started_at=datetime.now(timezone.utc),
        )
        message_uri = self.logger.log_message(
            "hola",
            message_id="schema_sender_shape",
            language="es",
            generated_by_activity=listening,
            sender=human,
        )
        graph = self.logger.graph
        self.assertIn((message_uri, SCHEMA.sender, human), graph)
        self.assertIn((message_uri, PROV.wasAttributedTo, human), graph)
        self.assertIn((message_uri, PROV.wasGeneratedBy, listening), graph)

    def test_activity_single_trigger_activity_is_logged(self) -> None:
        source_activity = self.logger.log_activity(
            activity_id="source_activity",
            activity_kind=ActivityKind.LISTENING,
            started_at=datetime.now(timezone.utc),
        )
        source_entity = self.logger.log_message(
            "source",
            message_id="source_message",
            generated_by_activity=source_activity,
            message_types=["oro:InitialMessage"],
            language="en",
        )

        target_activity = self.logger.log_activity(
            activity_id="target_activity",
            activity_kind=ActivityKind.DECISION,
            triggered_by_activity=source_activity,
            triggered_by_entity=source_entity,
            triggered_by_entities=[source_entity],
        )
        graph = self.logger.graph

        self.assertEqual(
            len(list(graph.objects(target_activity, SEGB.triggeredByActivity))),
            1,
        )
        self.assertEqual(
            len(list(graph.objects(target_activity, SEGB.triggeredByEntity))),
            1,
        )

    def test_activity_kind_maps_to_controlled_rdf_type(self) -> None:
        activity = self.logger.log_activity(
            activity_id="listen_by_kind",
            activity_kind=ActivityKind.LISTENING,
            started_at=datetime.now(timezone.utc),
        )
        self.assertIn((activity, RDF.type, ORO.ListeningEvent), self.logger.graph)

    def test_activity_kind_is_required(self) -> None:
        with self.assertRaises(ValueError):
            self.logger.log_activity(
                activity_id="strict_invalid",
                activity_kind=None,  # type: ignore[arg-type]
            )

    def test_activity_kind_accepts_extra_types(self) -> None:
        activity = self.logger.log_activity(
            activity_id="strict_ok",
            activity_kind=ActivityKind.DECISION,
            extra_types=["oro:CoordinationAction"],
        )

        graph = self.logger.graph
        self.assertIn((activity, RDF.type, ORO.DecisionMakingAction), graph)
        self.assertIn((activity, RDF.type, self.logger.resolve_term("oro:CoordinationAction")), graph)

    def test_emotions_and_robot_state(self) -> None:
        emotion_activity = self.logger.log_activity(
            activity_id="emotion_1",
            activity_kind=ActivityKind.EMOTION_RECOGNITION,
            started_at=datetime.now(timezone.utc),
        )
        msg = self.logger.log_message(
            "I am worried about climate change.",
            message_id="msg_1",
            generated_by_activity=emotion_activity,
            message_types=["oro:InitialMessage"],
            language="en",
        )
        human = self.logger.register_human("maria", first_name="Maria")

        annotation = self.logger.log_emotion_annotation(
            source_activity=emotion_activity,
            targets=[human, msg],
            emotions=[
                EmotionScore(category=EmotionCategory.FEAR, intensity=0.2, confidence=0.8),
                EmotionScore(category=EmotionCategory.SADNESS, intensity=0.6, confidence=0.9),
            ],
        )

        state = self.logger.log_robot_state(
            RobotStateSnapshot(
                timestamp=datetime.now(timezone.utc),
                battery_level=75.0,
                autonomy_mode="interactive",
                mission_phase="dialogue",
                cpu_load=29.5,
                memory_load=34.8,
                network_status="connected",
                location="https://example.org/rooms/lab1",
            ),
            source_activity=emotion_activity,
        )

        graph = self.logger.graph
        self.assertIn((annotation, RDF.type, AMOR.EmotionAnnotation), graph)
        self.assertIn((annotation, RDF.type, OA.Annotation), graph)
        self.assertIn((annotation, OA.hasTarget, human), graph)
        self.assertIn((annotation, OA.hasTarget, msg), graph)
        self.assertIn((emotion_activity, ONYX.usesEmotionModel, self.logger.resolve_term("emoml:big6")), graph)
        self.assertIn((emotion_activity, SEGB.producedEntityResult, state), graph)
        self.assertIn((state, PROV.wasAttributedTo, self.logger.robot_uri), graph)
        self.assertGreater(len(list(graph.objects(annotation, ONYX.hasEmotion))), 0)
        self.assertGreater(len(list(graph.objects(state, SCHEMA.additionalProperty))), 0)
        self.assertEqual(len(list(graph.objects(state, SCHEMA.location))), 0)
        self.assertGreater(len(list(graph.objects(state, PROV.atLocation))), 0)
        for emotion_uri in graph.objects(annotation, ONYX.hasEmotion):
            intensities = list(graph.objects(emotion_uri, ONYX.hasEmotionIntensity))
            self.assertGreater(len(intensities), 0)
            for intensity in intensities:
                self.assertIsInstance(intensity, Literal)
                self.assertEqual(intensity.datatype, XSD.float)
            confidences = list(graph.objects(emotion_uri, ONYX.algorithmConfidence))
            self.assertGreater(len(confidences), 0)
            for confidence in confidences:
                self.assertIsInstance(confidence, Literal)
                self.assertEqual(confidence.datatype, XSD.float)

    def test_result_typing_defaults_to_compatibility_dual_typing(self) -> None:
        state = self.logger.log_robot_state(
            RobotStateSnapshot(
                timestamp=datetime.now(timezone.utc),
            )
        )
        graph = self.logger.graph
        self.assertIn((state, RDF.type, PROV.Entity), graph)
        self.assertIn((state, RDF.type, SEGB.Result), graph)
        self.assertIn((state, RDF.type, PROV.Activity), graph)

    def test_robot_state_strict_mode_avoids_explicit_prov_activity(self) -> None:
        strict_logger = SemanticSEGBLogger(
            base_namespace="http://example.org/segb/robots/ari_strict/",
            robot_id="ari_strict",
            strict_result_typing=True,
        )
        state = strict_logger.log_robot_state(
            RobotStateSnapshot(
                timestamp=datetime.now(timezone.utc),
            )
        )
        graph = strict_logger.graph
        self.assertIn((state, RDF.type, PROV.Entity), graph)
        self.assertIn((state, RDF.type, SEGB.Result), graph)
        self.assertNotIn((state, RDF.type, PROV.Activity), graph)

    def test_emotion_annotation_strict_mode_avoids_explicit_prov_activity(self) -> None:
        strict_logger = SemanticSEGBLogger(
            base_namespace="http://example.org/segb/robots/ari_strict_emo/",
            robot_id="ari_strict_emo",
            strict_result_typing=True,
        )
        source_activity = strict_logger.log_activity(
            activity_id="strict_emotion_source",
            activity_kind=ActivityKind.EMOTION_RECOGNITION,
            started_at=datetime.now(timezone.utc),
        )
        target = strict_logger.register_human("strict_target_human")
        annotation = strict_logger.log_emotion_annotation(
            source_activity=source_activity,
            targets=[target],
            emotions=[EmotionScore(category=EmotionCategory.FEAR, intensity=0.5, confidence=0.8)],
        )
        graph = strict_logger.graph
        self.assertIn((annotation, RDF.type, PROV.Entity), graph)
        self.assertIn((annotation, RDF.type, SEGB.Result), graph)
        self.assertNotIn((annotation, RDF.type, PROV.Activity), graph)

    def test_emotion_category_rejects_unknown_plain_label(self) -> None:
        emotion_activity = self.logger.log_activity(
            activity_id="emotion_invalid_label",
            activity_kind=ActivityKind.EMOTION_RECOGNITION,
            started_at=datetime.now(timezone.utc),
        )
        with self.assertRaises(ValueError):
            self.logger.log_emotion_annotation(
                source_activity=emotion_activity,
                targets=[self.logger.robot_uri],
                emotions=[EmotionScore(category="bored", intensity=0.5)],
            )

    def test_cross_robot_links_in_shared_graph(self) -> None:
        shared_graph = Graph()
        ari = SemanticSEGBLogger(
            base_namespace="https://gsi.upm.es/segb/robots/ari/v1/",
            robot_id="ari1",
            graph=shared_graph,
        )
        tiago = SemanticSEGBLogger(
            base_namespace="https://gsi.upm.es/segb/robots/tiago/v1/",
            robot_id="tiago1",
            graph=shared_graph,
        )

        listening = ari.log_activity(
            activity_id="listening_1",
            activity_kind=ActivityKind.LISTENING,
            started_at=datetime.now(timezone.utc),
        )
        msg = ari.log_message(
            "Need climate headlines",
            message_id="msg_1",
            generated_by_activity=listening,
            message_types=["oro:InitialMessage"],
            language="en",
        )

        coordination = tiago.log_activity(
            activity_id="coordination_1",
            activity_kind=ActivityKind.DECISION,
            started_at=datetime.now(timezone.utc),
            triggered_by_entities=[msg],
            used_entities=[msg],
        )
        ari_decision = ari.log_activity(
            activity_id="decision_1",
            activity_kind=ActivityKind.DECISION,
            started_at=datetime.now(timezone.utc),
            triggered_by_activity=coordination,
            triggered_by_entities=[msg],
        )
        ari.link_influence(ari_decision, coordination)

        self.assertIn((coordination, SEGB.triggeredByEntity, msg), shared_graph)
        self.assertIn((coordination, PROV.wasInfluencedBy, msg), shared_graph)
        self.assertIn((ari_decision, SEGB.triggeredByActivity, coordination), shared_graph)
        self.assertIn((ari_decision, PROV.wasInfluencedBy, coordination), shared_graph)
        self.assertIn((listening, SEGB.producedEntityResult, msg), shared_graph)
        self.assertTrue(str(coordination).startswith("https://gsi.upm.es/segb/robots/tiago/v1/"))
        self.assertTrue(str(ari_decision).startswith("https://gsi.upm.es/segb/robots/ari/v1/"))

    def test_shared_event_resolution_and_observation_linking(self) -> None:
        human = self.logger.register_human("maria", first_name="Maria")
        observed_at = datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc)

        event_uri_1 = self.logger.resolve_shared_event(
            event_kind="human_utterance",
            observed_at=observed_at,
            subject=human,
            text="Hello world",
            modality="speech",
            time_bucket_seconds=2,
        )
        event_uri_2 = self.logger.resolve_shared_event(
            event_kind="human_utterance",
            observed_at=datetime(2026, 1, 1, 10, 0, 1, 900000, tzinfo=timezone.utc),
            subject=human,
            text=" hello   world ",
            modality="speech",
            time_bucket_seconds=2,
        )

        self.assertEqual(event_uri_1, event_uri_2)

        listening = self.logger.log_activity(
            activity_id="listening_shared_event",
            activity_kind=ActivityKind.LISTENING,
            started_at=observed_at,
            related_shared_events=[event_uri_1],
        )
        msg = self.logger.log_message(
            "hello world",
            message_id="msg_shared_event",
            generated_by_activity=listening,
            message_types=["oro:InitialMessage"],
            language="en",
        )
        self.logger.link_observation_to_shared_event(msg, event_uri_1, confidence=0.91)

        graph = self.logger.graph
        self.assertIn((event_uri_1, RDF.type, PROV.Entity), graph)
        self.assertIn((event_uri_1, RDF.type, SCHEMA.Event), graph)
        self.assertIn((listening, SCHEMA.about, event_uri_1), graph)
        self.assertIn((msg, PROV.specializationOf, event_uri_1), graph)
        confidence_properties = list(graph.objects(msg, SCHEMA.additionalProperty))
        self.assertGreater(len(confidence_properties), 0)
        for confidence_property in confidence_properties:
            self.assertIn((confidence_property, RDF.type, SCHEMA.PropertyValue), graph)
            self.assertIn((confidence_property, SCHEMA.propertyID, Literal("shared_event_confidence")), graph)
            values = list(graph.objects(confidence_property, SCHEMA.value))
            self.assertGreater(len(values), 0)
            for value in values:
                self.assertIsInstance(value, Literal)
                self.assertEqual(value.datatype, XSD.float)
        self.assertEqual(len(list(graph.objects(msg, SEGB.confidence))), 0)
        self.assertEqual(len(list(graph.objects(msg, SCHEMA.confidence))), 0)

    def test_shared_event_does_not_emit_non_standard_schema_properties(self) -> None:
        human = self.logger.register_human("maria_schema_strict", first_name="Maria")
        shared_event = self.logger.get_shared_event_uri(
            event_kind="human_utterance",
            observed_at=datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
            subject=human,
            text="hola",
            modality="speech",
        )

        graph = self.logger.graph
        self.assertEqual(len(list(graph.objects(shared_event, SCHEMA.measurementTechnique))), 0)
        self.assertEqual(len(list(graph.objects(shared_event, SCHEMA.eventType))), 0)

    def test_shared_event_models_modality_with_sosa(self) -> None:
        human = self.logger.register_human("maria_sosa_modality", first_name="Maria")
        shared_event = self.logger.get_shared_event_uri(
            event_kind="human_utterance",
            observed_at=datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
            subject=human,
            text="hola",
            modality="speech",
        )

        graph = self.logger.graph
        observations = list(graph.subjects(SOSA.hasFeatureOfInterest, shared_event))
        self.assertGreaterEqual(len(observations), 1)

        observation = observations[0]
        self.assertIn((observation, RDF.type, SOSA.Observation), graph)
        self.assertGreaterEqual(len(list(graph.objects(observation, SOSA.resultTime))), 1)

        procedures = list(graph.objects(observation, SOSA.usedProcedure))
        self.assertGreaterEqual(len(procedures), 1)
        procedure = procedures[0]
        self.assertIn((procedure, RDF.type, SOSA.Procedure), graph)
        labels = [str(value) for value in graph.objects(procedure, RDFS.label)]
        self.assertIn("speech", labels)

    def test_shared_event_keeps_single_event_metadata_when_event_id_is_reused(self) -> None:
        first_subject = self.logger.register_human("maria_shared_first", first_name="Maria")
        second_subject = self.logger.register_human("john_shared_second", first_name="John")
        first_time = datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc)
        second_time = datetime(2026, 1, 1, 10, 0, 7, tzinfo=timezone.utc)

        shared_event_1 = self.logger.get_shared_event_uri(
            event_kind="human_utterance",
            observed_at=first_time,
            subject=first_subject,
            text="hola",
            modality="speech",
            event_id="reused_event_id",
        )
        shared_event_2 = self.logger.get_shared_event_uri(
            event_kind="human_utterance",
            observed_at=second_time,
            subject=second_subject,
            text="adios",
            modality="speech",
            event_id="reused_event_id",
        )

        self.assertEqual(shared_event_1, shared_event_2)
        graph = self.logger.graph

        self.assertEqual(len(set(graph.objects(shared_event_1, PROV.generatedAtTime))), 1)
        self.assertEqual(len(set(graph.objects(shared_event_1, SCHEMA.description))), 1)
        self.assertEqual(len(set(graph.objects(shared_event_1, SCHEMA.about))), 1)

        # Different observations can still be linked to the same shared event.
        self.assertEqual(len(list(graph.subjects(SOSA.hasFeatureOfInterest, shared_event_1))), 2)

    def test_log_activity_rejects_reused_id_with_different_started_at(self) -> None:
        activity_id = "activity_reused_with_new_timestamp"
        self.logger.log_activity(
            activity_id=activity_id,
            activity_kind=ActivityKind.LISTENING,
            started_at=datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
        )

        with self.assertRaises(ValueError):
            self.logger.log_activity(
                activity_id=activity_id,
                activity_kind=ActivityKind.LISTENING,
                started_at=datetime(2026, 1, 1, 10, 0, 2, tzinfo=timezone.utc),
            )

    def test_get_shared_event_uri_uses_policy_fallback(self) -> None:
        human = self.logger.register_human("maria_policy", first_name="Maria")
        policy = SharedEventPolicy(
            namespace="https://gsi.upm.es/segb/shared-events/",
            time_bucket_seconds=2,
        )
        event_uri_1 = self.logger.get_shared_event_uri(
            event_kind="human_utterance",
            observed_at=datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
            subject=human,
            text="Hello world",
            modality="speech",
            policy=policy,
        )
        event_uri_2 = self.logger.get_shared_event_uri(
            event_kind="human_utterance",
            observed_at=datetime(2026, 1, 1, 10, 0, 1, 700000, tzinfo=timezone.utc),
            subject=human,
            text=" hello   world ",
            modality="speech",
            policy=policy,
        )

        self.assertEqual(event_uri_1, event_uri_2)
        self.assertTrue(str(event_uri_1).startswith("https://gsi.upm.es/segb/shared-events/"))

    def test_link_activity_to_shared_event_creates_contextual_relation(self) -> None:
        human = self.logger.register_human("maria_ctx", first_name="Maria")
        shared_event = self.logger.get_shared_event_uri(
            event_kind="human_utterance",
            observed_at=datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
            subject=human,
            text="hello",
            modality="speech",
        )
        activity = self.logger.log_activity(
            activity_id="contextual_activity",
            activity_kind=ActivityKind.LISTENING,
            started_at=datetime.now(timezone.utc),
        )
        self.logger.link_activity_to_shared_event(activity, shared_event)

        graph = self.logger.graph
        self.assertIn((activity, SCHEMA.about, shared_event), graph)
        self.assertIn((shared_event, RDF.type, PROV.Entity), graph)
        self.assertIn((shared_event, RDF.type, SCHEMA.Event), graph)

    def test_get_shared_event_uri_can_use_external_resolver(self) -> None:
        human = self.logger.register_human("maria_resolver", first_name="Maria")

        def resolver(request):  # type: ignore[no-untyped-def]
            self.assertEqual(request.event_kind, "human_utterance")
            self.assertEqual(request.subject, human)
            return "https://resolver.gsi.upm.es/shared-events/event_123"

        event_uri = self.logger.get_shared_event_uri(
            event_kind="human_utterance",
            observed_at=datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
            subject=human,
            text="hello world",
            modality="speech",
            resolver=resolver,
        )

        graph = self.logger.graph
        resolved = URIRef("https://resolver.gsi.upm.es/shared-events/event_123")
        self.assertEqual(event_uri, resolved)
        self.assertIn((resolved, RDF.type, PROV.Entity), graph)
        self.assertIn((resolved, RDF.type, SCHEMA.Event), graph)

    def test_logger_does_not_autoload_shared_context_from_env(self) -> None:
        with unittest.mock.patch.dict(
            os.environ,
            {
                "SEGB_API_URL": "https://segb.example.org",
                "SEGB_API_TOKEN": "token-123",
            },
            clear=False,
        ):
            logger = SemanticSEGBLogger(
                base_namespace="http://example.org/segb/robots/ari2/",
                robot_id="ari2",
            )
        self.assertIsNone(logger.shared_event_resolver)


if __name__ == "__main__":
    unittest.main()
