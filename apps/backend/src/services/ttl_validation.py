"""TTL syntax and semantic validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from rdflib import Graph, Literal, Namespace
from rdflib.exceptions import ParserError
from rdflib.namespace import RDF, XSD
from rdflib.term import Node

PROV = Namespace("http://www.w3.org/ns/prov#")
ONYX = Namespace("http://www.gsi.upm.es/ontologies/onyx/ns#")
SEGB = Namespace("http://www.gsi.upm.es/ontologies/segb/ns#")

NUMERIC_XSD_TYPES = {
    XSD.decimal,
    XSD.double,
    XSD.float,
    XSD.integer,
    XSD.int,
    XSD.long,
    XSD.short,
    XSD.byte,
    XSD.nonNegativeInteger,
    XSD.positiveInteger,
    XSD.nonPositiveInteger,
    XSD.negativeInteger,
    XSD.unsignedByte,
    XSD.unsignedShort,
    XSD.unsignedInt,
    XSD.unsignedLong,
}

OBJECT_PROPERTIES_MUST_POINT_TO_RESOURCE = (
    PROV.wasAssociatedWith,
    PROV.used,
    PROV.wasInfluencedBy,
    PROV.wasGeneratedBy,
    PROV.generated,
    PROV.specializationOf,
    SEGB.triggeredByActivity,
    SEGB.producedEntityResult,
)

TEMPORAL_PREDICATES_MUST_BE_DATETIME = (
    PROV.startedAtTime,
    PROV.endedAtTime,
    PROV.generatedAtTime,
)

SEMANTICALLY_RELEVANT_PREDICATES = set(OBJECT_PROPERTIES_MUST_POINT_TO_RESOURCE).union(
    TEMPORAL_PREDICATES_MUST_BE_DATETIME,
    {ONYX.hasEmotionIntensity, ONYX.hasEmotionCategory},
)


@dataclass(slots=True)
class TtlValidationIssue:
    severity: str
    code: str
    message: str
    focus_node: str | None = None
    predicate: str | None = None
    value: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "focus_node": self.focus_node,
            "predicate": self.predicate,
            "value": self.value,
        }


@dataclass(slots=True)
class TtlValidationResult:
    valid: bool
    syntax_ok: bool
    semantic_ok: bool
    triple_count: int
    issues: list[TtlValidationIssue]

    def to_payload(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "syntax_ok": self.syntax_ok,
            "semantic_ok": self.semantic_ok,
            "triple_count": self.triple_count,
            "issues": [issue.to_payload() for issue in self.issues],
        }


def _term_to_text(term: Node | None) -> str | None:
    if term is None:
        return None
    return str(term)


def _literal_to_decimal(literal: Literal) -> Decimal | None:
    if literal.datatype and literal.datatype in NUMERIC_XSD_TYPES:
        try:
            return Decimal(str(literal))
        except InvalidOperation:
            return None

    try:
        return Decimal(str(literal))
    except InvalidOperation:
        return None


def _graph_size(graph: Graph) -> int:
    """Returns triple count without relying on Graph.__len__ type stubs."""
    return sum(1 for _ in graph.triples((None, None, None)))


def _validate_rdf_type_object_resources(graph: Graph) -> list[TtlValidationIssue]:
    issues: list[TtlValidationIssue] = []
    for subject, _, object_ in graph.triples((None, RDF.type, None)):
        if isinstance(object_, Literal):
            issues.append(
                TtlValidationIssue(
                    severity="error",
                    code="SEM_RDF_TYPE_LITERAL",
                    message="rdf:type object must be an IRI resource, not a literal.",
                    focus_node=_term_to_text(subject),
                    predicate=str(RDF.type),
                    value=_term_to_text(object_),
                )
            )
    return issues


def _validate_object_property_targets(graph: Graph) -> list[TtlValidationIssue]:
    issues: list[TtlValidationIssue] = []
    for predicate in OBJECT_PROPERTIES_MUST_POINT_TO_RESOURCE:
        for subject, object_ in graph.subject_objects(predicate):
            if isinstance(object_, Literal):
                issues.append(
                    TtlValidationIssue(
                        severity="error",
                        code="SEM_OBJECT_PROPERTY_LITERAL",
                        message="This predicate must reference another resource (IRI or blank node), not a literal.",
                        focus_node=_term_to_text(subject),
                        predicate=_term_to_text(predicate),
                        value=_term_to_text(object_),
                    )
                )
    return issues


def _validate_temporal_literals(graph: Graph) -> list[TtlValidationIssue]:
    issues: list[TtlValidationIssue] = []
    for predicate in TEMPORAL_PREDICATES_MUST_BE_DATETIME:
        for subject, object_ in graph.subject_objects(predicate):
            if not isinstance(object_, Literal):
                issues.append(
                    TtlValidationIssue(
                        severity="error",
                        code="SEM_DATETIME_NOT_LITERAL",
                        message="Temporal predicate must use a literal with datatype xsd:dateTime.",
                        focus_node=_term_to_text(subject),
                        predicate=_term_to_text(predicate),
                        value=_term_to_text(object_),
                    )
                )
                continue

            if object_.datatype != XSD.dateTime:
                issues.append(
                    TtlValidationIssue(
                        severity="error",
                        code="SEM_DATETIME_WRONG_DATATYPE",
                        message="Temporal literal must be explicitly typed as xsd:dateTime.",
                        focus_node=_term_to_text(subject),
                        predicate=_term_to_text(predicate),
                        value=_term_to_text(object_),
                    )
                )
                continue

            parsed_value = object_.toPython()
            if not isinstance(parsed_value, datetime):
                issues.append(
                    TtlValidationIssue(
                        severity="error",
                        code="SEM_DATETIME_INVALID_LEXICAL",
                        message="Temporal literal has invalid xsd:dateTime lexical value.",
                        focus_node=_term_to_text(subject),
                        predicate=_term_to_text(predicate),
                        value=_term_to_text(object_),
                    )
                )
    return issues


def _validate_emotion_intensity(graph: Graph) -> list[TtlValidationIssue]:
    issues: list[TtlValidationIssue] = []
    for subject, object_ in graph.subject_objects(ONYX.hasEmotionIntensity):
        if not isinstance(object_, Literal):
            issues.append(
                TtlValidationIssue(
                    severity="error",
                    code="SEM_INTENSITY_NOT_LITERAL",
                    message="Emotion intensity must be a numeric literal between 0 and 1.",
                    focus_node=_term_to_text(subject),
                    predicate=_term_to_text(ONYX.hasEmotionIntensity),
                    value=_term_to_text(object_),
                )
            )
            continue

        value = _literal_to_decimal(object_)
        if value is None:
            issues.append(
                TtlValidationIssue(
                    severity="error",
                    code="SEM_INTENSITY_NOT_NUMERIC",
                    message="Emotion intensity must be numeric.",
                    focus_node=_term_to_text(subject),
                    predicate=_term_to_text(ONYX.hasEmotionIntensity),
                    value=_term_to_text(object_),
                )
            )
            continue

        if value < Decimal("0") or value > Decimal("1"):
            issues.append(
                TtlValidationIssue(
                    severity="error",
                    code="SEM_INTENSITY_OUT_OF_RANGE",
                    message="Emotion intensity must be between 0 and 1.",
                    focus_node=_term_to_text(subject),
                    predicate=_term_to_text(ONYX.hasEmotionIntensity),
                    value=_term_to_text(object_),
                )
            )
    return issues


def _validate_emotion_category_targets(graph: Graph) -> list[TtlValidationIssue]:
    issues: list[TtlValidationIssue] = []
    for subject, object_ in graph.subject_objects(ONYX.hasEmotionCategory):
        if isinstance(object_, Literal):
            issues.append(
                TtlValidationIssue(
                    severity="error",
                    code="SEM_EMOTION_CATEGORY_LITERAL",
                    message="Emotion category must reference a concept IRI, not a literal.",
                    focus_node=_term_to_text(subject),
                    predicate=_term_to_text(ONYX.hasEmotionCategory),
                    value=_term_to_text(object_),
                )
            )
    return issues


def _validate_semantic_subject_typing(graph: Graph) -> list[TtlValidationIssue]:
    issues: list[TtlValidationIssue] = []
    typed_subjects = set(graph.subjects(RDF.type, None))
    candidate_subjects = {
        subject
        for subject, predicate, _ in graph
        if predicate in SEMANTICALLY_RELEVANT_PREDICATES and subject not in typed_subjects
    }
    for subject in sorted(candidate_subjects, key=str):
        issues.append(
            TtlValidationIssue(
                severity="warning",
                code="SEM_SUBJECT_WITHOUT_TYPE",
                message="Node uses semantic predicates but has no rdf:type declaration.",
                focus_node=_term_to_text(subject),
            )
        )
    return issues


def _validate_semantics(graph: Graph, *, triple_count: int) -> list[TtlValidationIssue]:
    issues: list[TtlValidationIssue] = []

    if triple_count == 0:
        issues.append(
            TtlValidationIssue(
                severity="error",
                code="SEM_EMPTY_GRAPH",
                message="The Turtle document has no triples.",
            )
        )
        return issues

    validators = (
        _validate_rdf_type_object_resources,
        _validate_object_property_targets,
        _validate_temporal_literals,
        _validate_emotion_intensity,
        _validate_emotion_category_targets,
        _validate_semantic_subject_typing,
    )
    for validator in validators:
        issues.extend(validator(graph))

    return issues


def validate_ttl_content(ttl_content: str) -> TtlValidationResult:
    graph = Graph()
    try:
        graph.parse(data=ttl_content, format="turtle")
    except (ParserError, ValueError, SyntaxError) as error:
        syntax_message = str(error).strip() or "Invalid Turtle syntax."
        return TtlValidationResult(
            valid=False,
            syntax_ok=False,
            semantic_ok=False,
            triple_count=0,
            issues=[
                TtlValidationIssue(
                    severity="error",
                    code="TTL_SYNTAX_ERROR",
                    message=syntax_message,
                )
            ],
        )

    triple_count = _graph_size(graph)
    issues = _validate_semantics(graph, triple_count=triple_count)
    has_semantic_errors = any(issue.severity == "error" for issue in issues)
    return TtlValidationResult(
        valid=not has_semantic_errors,
        syntax_ok=True,
        semantic_ok=not has_semantic_errors,
        triple_count=triple_count,
        issues=issues,
    )
