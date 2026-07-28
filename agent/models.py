import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RequirementAnalysisValidationError(ValueError):
    """Raised when the LLM response cannot be used as requirement analysis."""


class TestPointValidationError(ValueError):
    """Raised when the LLM response cannot be used as structured test points."""


def _required_text(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise RequirementAnalysisValidationError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()


def _string_list(payload: dict[str, Any], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise RequirementAnalysisValidationError(
            f"{field_name} must be a list"
        )

    cleaned_items = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RequirementAnalysisValidationError(
                f"{field_name} must contain non-empty strings"
            )
        cleaned_items.append(item.strip())
    return cleaned_items


def _test_point_text(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise TestPointValidationError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()


def _test_point_string_list(
    payload: dict[str, Any],
    field_name: str,
) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list) or not value:
        raise TestPointValidationError(
            f"{field_name} must be a non-empty list"
        )

    cleaned_items = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise TestPointValidationError(
                f"{field_name} must contain non-empty strings"
            )
        cleaned_items.append(item.strip())
    return cleaned_items


@dataclass(frozen=True)
class InferredRisk:
    risk: str
    basis: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InferredRisk":
        if not isinstance(payload, dict):
            raise RequirementAnalysisValidationError(
                "each inferred risk must be an object"
            )
        return cls(
            risk=_required_text(payload, "risk"),
            basis=_required_text(payload, "basis"),
        )

    def to_dict(self) -> dict[str, str]:
        return {"risk": self.risk, "basis": self.basis}


@dataclass(frozen=True)
class RequirementAnalysisResult:
    summary: str
    modules: list[str] = field(default_factory=list)
    requirement_facts: list[str] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    state_transitions: list[str] = field(default_factory=list)
    inferred_risks: list[InferredRisk] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, raw_response: str) -> "RequirementAnalysisResult":
        cleaned_response = cls._strip_code_fence(raw_response)
        try:
            payload = json.loads(cleaned_response)
        except json.JSONDecodeError as exc:
            raise RequirementAnalysisValidationError(
                "LLM response is not valid JSON: "
                f"{exc.msg} (line {exc.lineno}, column {exc.colno})"
            ) from exc

        if not isinstance(payload, dict):
            raise RequirementAnalysisValidationError(
                "LLM response must be a JSON object"
            )
        return cls.from_dict(payload)

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "RequirementAnalysisResult":
        expected_fields = {
            "summary",
            "modules",
            "requirement_facts",
            "business_rules",
            "state_transitions",
            "inferred_risks",
            "open_questions",
        }
        unexpected_fields = set(payload) - expected_fields
        if unexpected_fields:
            raise RequirementAnalysisValidationError(
                "unexpected fields: "
                + ", ".join(sorted(unexpected_fields))
            )

        risk_payload = payload.get("inferred_risks")
        if not isinstance(risk_payload, list):
            raise RequirementAnalysisValidationError(
                "inferred_risks must be a list"
            )

        return cls(
            summary=_required_text(payload, "summary"),
            modules=_string_list(payload, "modules"),
            requirement_facts=_string_list(
                payload,
                "requirement_facts",
            ),
            business_rules=_string_list(payload, "business_rules"),
            state_transitions=_string_list(
                payload,
                "state_transitions",
            ),
            inferred_risks=[
                InferredRisk.from_dict(item) for item in risk_payload
            ],
            open_questions=_string_list(payload, "open_questions"),
        )

    @staticmethod
    def _strip_code_fence(raw_response: str) -> str:
        cleaned = raw_response.strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return cleaned

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "modules": self.modules,
            "requirement_facts": self.requirement_facts,
            "business_rules": self.business_rules,
            "state_transitions": self.state_transitions,
            "inferred_risks": [
                risk.to_dict() for risk in self.inferred_risks
            ],
            "open_questions": self.open_questions,
        }


class TestPointCategory(str, Enum):
    FUNCTIONAL = "functional"
    BOUNDARY = "boundary"
    EXCEPTION = "exception"
    NON_FUNCTIONAL = "non_functional"


class TestPointPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class TestPointSource(str, Enum):
    REQUIREMENT = "requirement"
    HISTORICAL_ASSET = "historical_asset"
    TEST_EXPERIENCE = "test_experience"
    USER_FEEDBACK = "user_feedback"


@dataclass(frozen=True)
class TestPoint:
    title: str
    category: TestPointCategory
    priority: TestPointPriority
    scenario: str
    preconditions: list[str]
    steps: list[str]
    expected_results: list[str]
    sources: list[TestPointSource]
    source_refs: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TestPoint":
        if not isinstance(payload, dict):
            raise TestPointValidationError(
                "each test point must be an object"
            )

        expected_fields = {
            "title",
            "category",
            "priority",
            "scenario",
            "preconditions",
            "steps",
            "expected_results",
            "sources",
            "source_refs",
        }
        unexpected_fields = set(payload) - expected_fields
        if unexpected_fields:
            raise TestPointValidationError(
                "unexpected test point fields: "
                + ", ".join(sorted(unexpected_fields))
            )

        try:
            category = TestPointCategory(
                _test_point_text(payload, "category")
            )
        except ValueError as exc:
            raise TestPointValidationError(
                "category must be functional, boundary, exception, "
                "or non_functional"
            ) from exc

        try:
            priority = TestPointPriority(
                _test_point_text(payload, "priority")
            )
        except ValueError as exc:
            raise TestPointValidationError(
                "priority must be P0, P1, or P2"
            ) from exc

        raw_sources = _test_point_string_list(payload, "sources")
        try:
            sources = [TestPointSource(item) for item in raw_sources]
        except ValueError as exc:
            raise TestPointValidationError(
                "sources contain an unsupported value"
            ) from exc

        return cls(
            title=_test_point_text(payload, "title"),
            category=category,
            priority=priority,
            scenario=_test_point_text(payload, "scenario"),
            preconditions=_test_point_string_list(
                payload,
                "preconditions",
            ),
            steps=_test_point_string_list(payload, "steps"),
            expected_results=_test_point_string_list(
                payload,
                "expected_results",
            ),
            sources=sources,
            source_refs=_test_point_string_list(
                payload,
                "source_refs",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "category": self.category.value,
            "priority": self.priority.value,
            "scenario": self.scenario,
            "preconditions": list(self.preconditions),
            "steps": list(self.steps),
            "expected_results": list(self.expected_results),
            "sources": [source.value for source in self.sources],
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class TestPointGenerationResult:
    test_points: list[TestPoint]

    @classmethod
    def from_json(cls, raw_response: str) -> "TestPointGenerationResult":
        cleaned_response = RequirementAnalysisResult._strip_code_fence(
            raw_response
        )
        try:
            payload = json.loads(cleaned_response)
        except json.JSONDecodeError as exc:
            raise TestPointValidationError(
                "LLM response is not valid JSON: "
                f"{exc.msg} (line {exc.lineno}, column {exc.colno})"
            ) from exc

        if not isinstance(payload, dict):
            raise TestPointValidationError(
                "LLM response must be a JSON object"
            )
        if set(payload) != {"test_points"}:
            raise TestPointValidationError(
                "top-level JSON must contain only test_points"
            )

        raw_test_points = payload["test_points"]
        if not isinstance(raw_test_points, list) or not raw_test_points:
            raise TestPointValidationError(
                "test_points must be a non-empty list"
            )
        return cls(
            test_points=[
                TestPoint.from_dict(item) for item in raw_test_points
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_points": [
                test_point.to_dict() for test_point in self.test_points
            ]
        }
