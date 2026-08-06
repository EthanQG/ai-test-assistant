"""Versioned, human-authored contracts for offline evaluation cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.models import ClarificationCategory


SCHEMA_VERSION = 1


class EvaluationDatasetError(ValueError):
    """Raised when an evaluation dataset violates the annotation contract."""


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvaluationDatasetError(f"{path} must be an object")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationDatasetError(f"{path} must be a non-empty string")
    return value.strip()


def _items(value: Any, path: str, *, allow_empty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        raise EvaluationDatasetError(f"{path} must be a list")
    if not allow_empty and not value:
        raise EvaluationDatasetError(f"{path} must not be empty")
    return value


def _fields(payload: dict[str, Any], expected: set[str], path: str) -> None:
    missing = expected - set(payload)
    unknown = set(payload) - expected
    if missing:
        raise EvaluationDatasetError(
            f"{path} missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise EvaluationDatasetError(
            f"{path} has unknown fields: {', '.join(sorted(unknown))}"
        )


@dataclass(frozen=True)
class Annotation:
    """One expected fact, rule, risk, or scenario and its source evidence."""

    text: str
    evidence: str

    @classmethod
    def from_dict(cls, value: Any, path: str) -> "Annotation":
        payload = _object(value, path)
        _fields(payload, {"text", "evidence"}, path)
        return cls(
            text=_text(payload["text"], f"{path}.text"),
            evidence=_text(payload["evidence"], f"{path}.evidence"),
        )


@dataclass(frozen=True)
class ClarificationAnnotation:
    """A question that should be raised because the input is insufficient."""

    question: str
    category: ClarificationCategory
    evidence: str

    @classmethod
    def from_dict(cls, value: Any, path: str) -> "ClarificationAnnotation":
        payload = _object(value, path)
        _fields(payload, {"question", "category", "evidence"}, path)
        raw_category = _text(payload["category"], f"{path}.category")
        try:
            category = ClarificationCategory(raw_category)
        except ValueError as exc:
            raise EvaluationDatasetError(
                f"{path}.category is unsupported: {raw_category}"
            ) from exc
        return cls(
            question=_text(payload["question"], f"{path}.question"),
            category=category,
            evidence=_text(payload["evidence"], f"{path}.evidence"),
        )


@dataclass(frozen=True)
class GoldAnnotations:
    """Human-reviewed expectations used as the evaluation gold standard."""

    facts: tuple[Annotation, ...]
    business_rules: tuple[Annotation, ...]
    risks: tuple[Annotation, ...]
    clarification_questions: tuple[ClarificationAnnotation, ...]
    necessary_scenarios: tuple[Annotation, ...]
    forbidden_assertions: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, path: str) -> "GoldAnnotations":
        payload = _object(value, path)
        fields = {
            "facts",
            "business_rules",
            "risks",
            "clarification_questions",
            "necessary_scenarios",
            "forbidden_assertions",
        }
        _fields(payload, fields, path)

        def annotations(name: str) -> tuple[Annotation, ...]:
            values = _items(payload[name], f"{path}.{name}")
            return tuple(
                Annotation.from_dict(item, f"{path}.{name}[{index}]")
                for index, item in enumerate(values)
            )

        questions = _items(
            payload["clarification_questions"],
            f"{path}.clarification_questions",
            allow_empty=True,
        )
        forbidden = _items(
            payload["forbidden_assertions"],
            f"{path}.forbidden_assertions",
        )
        return cls(
            facts=annotations("facts"),
            business_rules=annotations("business_rules"),
            risks=annotations("risks"),
            clarification_questions=tuple(
                ClarificationAnnotation.from_dict(
                    item, f"{path}.clarification_questions[{index}]"
                )
                for index, item in enumerate(questions)
            ),
            necessary_scenarios=annotations("necessary_scenarios"),
            forbidden_assertions=tuple(
                _text(item, f"{path}.forbidden_assertions[{index}]")
                for index, item in enumerate(forbidden)
            ),
        )


@dataclass(frozen=True)
class EvaluationCase:
    """A synthetic requirement and its independently reviewed annotations."""

    case_id: str
    title: str
    domain: str
    source_format: str
    document_features: tuple[str, ...]
    requirement: str
    gold: GoldAnnotations

    @classmethod
    def from_dict(cls, value: Any, path: str) -> "EvaluationCase":
        payload = _object(value, path)
        fields = {
            "case_id",
            "title",
            "domain",
            "source_format",
            "document_features",
            "requirement",
            "gold",
        }
        _fields(payload, fields, path)
        features = _items(
            payload["document_features"],
            f"{path}.document_features",
            allow_empty=True,
        )
        return cls(
            case_id=_text(payload["case_id"], f"{path}.case_id"),
            title=_text(payload["title"], f"{path}.title"),
            domain=_text(payload["domain"], f"{path}.domain"),
            source_format=_text(payload["source_format"], f"{path}.source_format"),
            document_features=tuple(
                _text(item, f"{path}.document_features[{index}]")
                for index, item in enumerate(features)
            ),
            requirement=_text(payload["requirement"], f"{path}.requirement"),
            gold=GoldAnnotations.from_dict(payload["gold"], f"{path}.gold"),
        )


@dataclass(frozen=True)
class EvaluationDataset:
    schema_version: int
    dataset_id: str
    description: str
    cases: tuple[EvaluationCase, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "EvaluationDataset":
        payload = _object(value, "dataset")
        _fields(
            payload,
            {"schema_version", "dataset_id", "description", "cases"},
            "dataset",
        )
        if (
            not isinstance(payload["schema_version"], int)
            or isinstance(payload["schema_version"], bool)
            or payload["schema_version"] != SCHEMA_VERSION
        ):
            raise EvaluationDatasetError(
                f"unsupported schema_version: {payload['schema_version']}"
            )
        raw_cases = _items(payload["cases"], "dataset.cases")
        cases = tuple(
            EvaluationCase.from_dict(item, f"dataset.cases[{index}]")
            for index, item in enumerate(raw_cases)
        )
        case_ids = [case.case_id for case in cases]
        if len(case_ids) != len(set(case_ids)):
            raise EvaluationDatasetError("dataset.case_id values must be unique")
        return cls(
            schema_version=SCHEMA_VERSION,
            dataset_id=_text(payload["dataset_id"], "dataset.dataset_id"),
            description=_text(payload["description"], "dataset.description"),
            cases=cases,
        )


def load_evaluation_dataset(path: str | Path) -> EvaluationDataset:
    """Load and validate a UTF-8 JSON dataset without calling external services."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationDatasetError(f"cannot load evaluation dataset: {exc}") from exc
    return EvaluationDataset.from_dict(payload)
