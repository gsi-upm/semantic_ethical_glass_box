"""Use case 02: build a report-ready dataset from the base interaction."""

from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.simulations.bootstrap import configure_pythonpath

configure_pythonpath()

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from rdflib import Graph, URIRef

from examples.simulations.cli_common import add_publish_arguments, add_ttl_output_arguments, graph_to_ttl_text, write_ttl_output
from examples.simulations.run_simulation import (
    ARI_NAMESPACE,
    TIAGO_NAMESPACE,
    PublishConfig,
    SimulationResult,
    build_publish_config_from_args,
    build_shared_event_resolver,
    publish_graph,
    run_basic_simulation,
)
from semantic_log_generator import ActivityKind, EmotionScore, RobotStateSnapshot, SemanticSEGBLogger, SharedEventResolver
from semantic_log_generator.namespaces import EMOML, ORO


@dataclass(slots=True)
class ReportReadySimulationResult:
    """Artifacts generated for the report-ready dataset use case."""

    graph: Graph
    base_result: SimulationResult
    base_timestamp: datetime


@dataclass(slots=True)
class ReportLoggers:
    ari: SemanticSEGBLogger
    tiago: SemanticSEGBLogger


@dataclass(slots=True)
class ReportModels:
    asr: URIRef
    emotion: URIRef
    vision: URIRef


@dataclass(slots=True)
class ConversationArtifacts:
    base_timestamp: datetime
    cheer_request_shared_event: URIRef
    gratitude_listening_activity: URIRef


@dataclass(slots=True)
class CheerRequestFlow:
    base_timestamp: datetime
    shared_event_uri: URIRef
    listening_activity_uri: URIRef
    heard_message_uri: URIRef


@dataclass(slots=True)
class AnxietyFlow:
    exam_news_message_uri: URIRef
    anxiety_face_observation_uri: URIRef
    anxiety_activity_uri: URIRef


@dataclass(slots=True)
class RecoveryDialogueFlow:
    gratitude_listening_activity_uri: URIRef


def _build_report_loggers(
    base_result: SimulationResult,
    *,
    shared_event_resolver: SharedEventResolver | None,
) -> ReportLoggers:
    ari_logger = SemanticSEGBLogger(
        base_namespace=ARI_NAMESPACE,
        robot_id="ari1",
        robot_name="ARI",
        graph=base_result.graph,
        namespace_prefix="ari",
        compact_resource_ids=True,
        shared_event_resolver=shared_event_resolver,
    )
    tiago_logger = SemanticSEGBLogger(
        base_namespace=TIAGO_NAMESPACE,
        robot_id="tiago1",
        robot_name="TIAGo",
        graph=base_result.graph,
        namespace_prefix="tiago",
        compact_resource_ids=True,
        shared_event_resolver=shared_event_resolver,
    )
    return ReportLoggers(ari=ari_logger, tiago=tiago_logger)


def _register_models(ari_logger: SemanticSEGBLogger) -> ReportModels:
    asr_model = ari_logger.register_ml_model("asr_vosk_es", label="ASR Vosk ES", version="0.3")
    emotion_model = ari_logger.register_ml_model("emotion_big6_v1", label="Emotion Big6 CNN", version="1.0")
    vision_model = ari_logger.register_ml_model(
        "vision_human_detector_v1",
        label="Human Detector",
        version="2.1",
    )
    return ReportModels(asr=asr_model, emotion=emotion_model, vision=vision_model)


def _log_model_training(ari_logger: SemanticSEGBLogger, models: ReportModels) -> None:
    dataset_uri = ari_logger.register_dataset("emotion_dataset_v1", label="EmotionDataset v1")
    eval_uri = ari_logger.register_model_evaluation(
        "emotion_accuracy_eval_1",
        value=0.89,
    )

    train_run = ari_logger.log_activity(
        activity_id="emotion_model_training_run_1",
        activity_kind=ActivityKind.ML_RUN,
        started_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        ended_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        used_models=[models.emotion],
        used_entities=[dataset_uri],
        produced_entity_results=[models.emotion, eval_uri],
    )
    ari_logger.link_ml_run_input(train_run, dataset_uri)
    ari_logger.link_ml_run_output(train_run, models.emotion)
    ari_logger.link_ml_run_output(train_run, eval_uri)


def _log_conversation_sequence(
    *,
    ari_logger: SemanticSEGBLogger,
    human_uri: URIRef,
    base_result: SimulationResult,
    models: ReportModels,
) -> ConversationArtifacts:
    cheer_request = _log_cheer_request_start(
        ari_logger=ari_logger,
        human_uri=human_uri,
        base_result=base_result,
        asr_model=models.asr,
        vision_model=models.vision,
    )
    anxiety = _log_exam_news_and_anxiety(
        ari_logger=ari_logger,
        human_uri=human_uri,
        emotion_model=models.emotion,
        cheer_request=cheer_request,
    )
    recovery = _log_recovery_dialogue(
        ari_logger=ari_logger,
        cheer_request=cheer_request,
        anxiety=anxiety,
        asr_model=models.asr,
    )
    return ConversationArtifacts(
        base_timestamp=cheer_request.base_timestamp,
        cheer_request_shared_event=cheer_request.shared_event_uri,
        gratitude_listening_activity=recovery.gratitude_listening_activity_uri,
    )


def _log_cheer_request_start(
    *,
    ari_logger: SemanticSEGBLogger,
    human_uri: URIRef,
    base_result: SimulationResult,
    asr_model: URIRef,
    vision_model: URIRef,
) -> CheerRequestFlow:
    ari_listening_activity = ari_logger.resource_uri("activity", "ari_listening_1")
    ari_logger.link_activity_model(ari_listening_activity, asr_model)

    ari_logger.log_activity(
        activity_id="vision_perception_1",
        activity_kind=ActivityKind.HUMAN_DETECTION,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        used_models=[vision_model],
        related_shared_events=[base_result.shared_event_uri],
    )

    base_t = datetime.now(timezone.utc) - timedelta(minutes=10)

    cheer_request_shared_event = ari_logger.get_shared_event_uri(
        event_kind="human_utterance",
        observed_at=base_t,
        subject=human_uri,
        text="ARI, can you show me a piece of news to cheer me up?",
        modality="speech",
    )

    cheer_request_listening_activity = ari_logger.log_activity(
        activity_id="ari_listening_cheer_request_1",
        activity_kind=ActivityKind.LISTENING,
        started_at=base_t,
        ended_at=base_t + timedelta(seconds=5),
        triggered_by_activity=ari_listening_activity,
        triggered_by_entity=base_result.ari_response_uri,
        related_shared_events=[cheer_request_shared_event],
        used_entities=[base_result.ari_response_uri],
        used_models=[asr_model],
    )
    cheer_request_message = ari_logger.log_message(
        "ARI, can you show me some news to cheer me up?",
        message_id="ari_heard_cheer_request_1",
        generated_by_activity=cheer_request_listening_activity,
        message_types=[ORO.InitialMessage],
        language="en",
        previous_message=base_result.ari_response_uri,
    )
    ari_logger.link_observation_to_shared_event(cheer_request_message, cheer_request_shared_event, confidence=0.95)
    return CheerRequestFlow(
        base_timestamp=base_t,
        shared_event_uri=cheer_request_shared_event,
        listening_activity_uri=cheer_request_listening_activity,
        heard_message_uri=cheer_request_message,
    )


def _log_exam_news_and_anxiety(
    *,
    ari_logger: SemanticSEGBLogger,
    human_uri: URIRef,
    emotion_model: URIRef,
    cheer_request: CheerRequestFlow,
) -> AnxietyFlow:
    exam_news_activity = ari_logger.log_activity(
        activity_id="ari_exam_news_response_1",
        activity_kind=ActivityKind.RESPONSE,
        started_at=cheer_request.base_timestamp + timedelta(seconds=10),
        ended_at=cheer_request.base_timestamp + timedelta(seconds=15),
        triggered_by_activity=cheer_request.listening_activity_uri,
        triggered_by_entity=cheer_request.heard_message_uri,
        related_shared_events=[cheer_request.shared_event_uri],
        used_entities=[cheer_request.heard_message_uri],
    )
    exam_news_message = ari_logger.log_message(
        "Here is one headline: many students are anxious because an important exam is coming soon.",
        message_id="ari_exam_news_msg_1",
        generated_by_activity=exam_news_activity,
        message_types=[ORO.ResponseMessage],
        previous_message=cheer_request.heard_message_uri,
    )

    anxiety_face_observation = ari_logger.log_observation(
        observation_id="ari_face_anxiety_after_exam_1",
        label="Face snapshot after exam news",
        related_shared_event=cheer_request.shared_event_uri,
        confidence=0.93,
        mark_as_result=True,
    )

    anxiety_activity = ari_logger.log_activity(
        activity_id="emotion_analysis_1",
        activity_kind=ActivityKind.EMOTION_ANALYSIS,
        extra_types=[ORO.EmotionRecognitionEvent],
        label="Maria anxiety detected after exam news",
        started_at=cheer_request.base_timestamp + timedelta(minutes=1),
        ended_at=cheer_request.base_timestamp + timedelta(minutes=1, seconds=5),
        used_models=[emotion_model],
        related_shared_events=[cheer_request.shared_event_uri],
        triggered_by_entity=anxiety_face_observation,
        used_entities=[anxiety_face_observation],
    )
    ari_logger.log_emotion_annotation(
        source_activity=anxiety_activity,
        targets=[human_uri, ari_logger.robot_uri],
        emotions=[
            EmotionScore(
                category=EMOML.big6_fear,
                intensity=0.90,
                confidence=0.95,
            ),
        ],
        emotion_model=EMOML.big6,
    )
    return AnxietyFlow(
        exam_news_message_uri=exam_news_message,
        anxiety_face_observation_uri=anxiety_face_observation,
        anxiety_activity_uri=anxiety_activity,
    )


def _log_recovery_dialogue(
    *,
    ari_logger: SemanticSEGBLogger,
    cheer_request: CheerRequestFlow,
    anxiety: AnxietyFlow,
    asr_model: URIRef,
) -> RecoveryDialogueFlow:
    apology_activity = ari_logger.log_activity(
        activity_id="ari_apology_response_1",
        activity_kind=ActivityKind.RESPONSE,
        started_at=cheer_request.base_timestamp + timedelta(minutes=2),
        ended_at=cheer_request.base_timestamp + timedelta(minutes=2, seconds=5),
        triggered_by_activity=anxiety.anxiety_activity_uri,
        triggered_by_entity=anxiety.anxiety_face_observation_uri,
        related_shared_events=[cheer_request.shared_event_uri],
        used_entities=[anxiety.anxiety_face_observation_uri],
    )
    apology_message = ari_logger.log_message(
        "I am sorry, Maria. That exam news was not a good choice right now.",
        message_id="ari_apology_msg_1",
        generated_by_activity=apology_activity,
        message_types=[ORO.ResponseMessage],
        previous_message=anxiety.exam_news_message_uri,
    )

    animal_news_activity = ari_logger.log_activity(
        activity_id="ari_animal_news_response_1",
        activity_kind=ActivityKind.RESPONSE,
        started_at=cheer_request.base_timestamp + timedelta(minutes=2, seconds=20),
        ended_at=cheer_request.base_timestamp + timedelta(minutes=2, seconds=25),
        triggered_by_activity=apology_activity,
        triggered_by_entity=apology_message,
        related_shared_events=[cheer_request.shared_event_uri],
        used_entities=[apology_message],
    )
    animal_news_message = ari_logger.log_message(
        "Here is another one: a rescue center found homes for twenty puppies this weekend.",
        message_id="ari_animal_news_msg_1",
        generated_by_activity=animal_news_activity,
        message_types=[ORO.ResponseMessage],
        previous_message=apology_message,
    )

    gratitude_listening_activity = ari_logger.log_activity(
        activity_id="ari_listening_gratitude_1",
        activity_kind=ActivityKind.LISTENING,
        started_at=cheer_request.base_timestamp + timedelta(minutes=3),
        ended_at=cheer_request.base_timestamp + timedelta(minutes=3, seconds=5),
        triggered_by_activity=animal_news_activity,
        triggered_by_entity=animal_news_message,
        related_shared_events=[cheer_request.shared_event_uri],
        used_entities=[animal_news_message],
        used_models=[asr_model],
    )
    gratitude_message = ari_logger.log_message(
        "Thank you, ARI! That animal news made me very happy.",
        message_id="ari_heard_gratitude_1",
        generated_by_activity=gratitude_listening_activity,
        message_types=[ORO.InitialMessage],
        language="en",
        previous_message=animal_news_message,
    )
    ari_logger.link_observation_to_shared_event(gratitude_message, cheer_request.shared_event_uri, confidence=0.97)
    return RecoveryDialogueFlow(gratitude_listening_activity_uri=gratitude_listening_activity)


def _log_recovery_emotion(
    *,
    ari_logger: SemanticSEGBLogger,
    human_uri: URIRef,
    models: ReportModels,
    conversation: ConversationArtifacts,
) -> None:
    very_happy_face_observation = ari_logger.log_observation(
        observation_id="ari_face_very_happy_1",
        label="Face snapshot after animal news",
        related_shared_event=conversation.cheer_request_shared_event,
        confidence=0.96,
        mark_as_result=True,
    )

    very_happy_activity = ari_logger.log_activity(
        activity_id="emotion_analysis_2",
        activity_kind=ActivityKind.EMOTION_ANALYSIS,
        extra_types=[ORO.EmotionRecognitionEvent],
        label="Maria very happy after animal news",
        started_at=conversation.base_timestamp + timedelta(minutes=4),
        ended_at=conversation.base_timestamp + timedelta(minutes=4, seconds=5),
        used_models=[models.emotion],
        related_shared_events=[conversation.cheer_request_shared_event],
        triggered_by_activity=conversation.gratitude_listening_activity,
        triggered_by_entity=very_happy_face_observation,
        used_entities=[very_happy_face_observation],
    )
    ari_logger.log_emotion_annotation(
        source_activity=very_happy_activity,
        targets=[human_uri, ari_logger.robot_uri],
        emotions=[
            EmotionScore(
                category=EMOML.big6_happiness,
                intensity=0.98,
                confidence=0.96,
            ),
        ],
        emotion_model=EMOML.big6,
    )


def _log_robot_state_history(
    *,
    ari_logger: SemanticSEGBLogger,
    tiago_logger: SemanticSEGBLogger,
    base_timestamp: datetime,
) -> None:
    room_a = ari_logger.resource_uri("location", "room_a")
    room_b = ari_logger.resource_uri("location", "room_b")
    room_c = ari_logger.resource_uri("location", "room_c")

    ari_logger.log_robot_state(
        RobotStateSnapshot(
            timestamp=base_timestamp + timedelta(minutes=1),
            location=room_a,
            battery_level=0.82,
            mission_phase="listen",
        ),
        state_id="ari_state_1",
    )
    ari_logger.log_robot_state(
        RobotStateSnapshot(
            timestamp=base_timestamp + timedelta(minutes=3),
            location=room_b,
            battery_level=0.79,
            mission_phase="respond",
        ),
        state_id="ari_state_2",
    )
    tiago_logger.log_robot_state(
        RobotStateSnapshot(
            timestamp=base_timestamp + timedelta(minutes=1),
            location=room_b,
            battery_level=0.74,
            mission_phase="listen",
        ),
        state_id="tiago_state_1",
    )
    tiago_logger.log_robot_state(
        RobotStateSnapshot(
            timestamp=base_timestamp + timedelta(minutes=4),
            location=room_c,
            battery_level=0.72,
            mission_phase="idle",
        ),
        state_id="tiago_state_2",
    )


def enrich_report_ready_graph(
    base_result: SimulationResult,
    *,
    shared_event_resolver: SharedEventResolver | None = None,
) -> datetime:
    """Adds report-oriented data on top of the base interaction graph."""
    loggers = _build_report_loggers(base_result, shared_event_resolver=shared_event_resolver)
    human_uri = base_result.human_uri

    models = _register_models(loggers.ari)
    _log_model_training(loggers.ari, models)

    conversation = _log_conversation_sequence(
        ari_logger=loggers.ari,
        human_uri=human_uri,
        base_result=base_result,
        models=models,
    )
    _log_recovery_emotion(
        ari_logger=loggers.ari,
        human_uri=human_uri,
        models=models,
        conversation=conversation,
    )
    _log_robot_state_history(
        ari_logger=loggers.ari,
        tiago_logger=loggers.tiago,
        base_timestamp=conversation.base_timestamp,
    )

    return conversation.base_timestamp


def run_report_ready_simulation(
    *,
    shared_event_resolver: SharedEventResolver | None = None,
) -> ReportReadySimulationResult:
    """Runs use case 02 (base interaction + report-oriented enrichment)."""
    base_result = run_basic_simulation(shared_event_resolver=shared_event_resolver)
    base_timestamp = enrich_report_ready_graph(base_result, shared_event_resolver=shared_event_resolver)
    return ReportReadySimulationResult(
        graph=base_result.graph,
        base_result=base_result,
        base_timestamp=base_timestamp,
    )


def publish_report_ready_simulation_result(
    simulation_result: ReportReadySimulationResult,
    *,
    config: PublishConfig,
) -> dict[str, object]:
    """Publishes use case 02 graph into SEGB backend."""
    return publish_graph(simulation_result.graph, config=config)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run use case 02 (report-ready dataset), optionally publish to SEGB, and optionally export Turtle."
    )
    add_ttl_output_arguments(parser)
    add_publish_arguments(parser, include_no_publish=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    publish_config = None if args.no_publish else build_publish_config_from_args(args)
    shared_event_resolver = build_shared_event_resolver(publish_config)

    result = run_report_ready_simulation(shared_event_resolver=shared_event_resolver)

    if publish_config is not None:
        report = publish_report_ready_simulation_result(result, config=publish_config)
        print(json.dumps(report, ensure_ascii=True, indent=2))

    ttl_text = graph_to_ttl_text(result.graph)
    output_path = write_ttl_output(ttl_text, args.ttl_output)
    if output_path is not None:
        print(f"Wrote Turtle to: {output_path}")

    print("Use case: 02-report-ready-dataset")
    print(f"SharedEvent URI (base interaction): {result.base_result.shared_event_uri}")
    print(f"Triples generated: {len(result.graph)}")

    if not args.no_print_ttl:
        print(ttl_text)


if __name__ == "__main__":
    main()
