import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RequirementAnalysisValidationError(ValueError):
    """Raised when the LLM response cannot be used as requirement analysis."""


class TestPointValidationError(ValueError):
    """Raised when the LLM response cannot be used as structured test points."""


class ClarificationCategory(str, Enum):
    CORE_RULE = "core_rule"
    CRITICAL_VALUE = "critical_value"
    FLOW_BRANCH = "flow_branch"
    REQUIREMENT_CONFLICT = "requirement_conflict"
    IMPLEMENTATION_DETAIL = "implementation_detail"
    LOW_IMPACT = "low_impact"


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
class ClarificationCandidate:
    question: str
    category: ClarificationCategory
    blocking_reason: str
    evidence: str

    @classmethod
    def from_dict(
        cls, payload: dict[str, Any]
    ) -> "ClarificationCandidate":
        if not isinstance(payload, dict):
            raise RequirementAnalysisValidationError(
                "each open question must be an object"
            )
        expected_fields = {
            "question",
            "category",
            "blocking_reason",
            "evidence",
        }
        if set(payload) != expected_fields:
            raise RequirementAnalysisValidationError(
                "open question fields are invalid"
            )
        try:
            category = ClarificationCategory(
                _required_text(payload, "category")
            )
        except ValueError as exc:
            raise RequirementAnalysisValidationError(
                "open question category is unsupported"
            ) from exc
        return cls(
            question=_required_text(payload, "question"),
            category=category,
            blocking_reason=_required_text(payload, "blocking_reason"),
            evidence=_required_text(payload, "evidence"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "question": self.question,
            "category": self.category.value,
            "blocking_reason": self.blocking_reason,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class RequirementAnalysisResult:
    summary: str
    modules: list[str] = field(default_factory=list)
    requirement_facts: list[str] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    state_transitions: list[str] = field(default_factory=list)
    inferred_risks: list[InferredRisk] = field(default_factory=list)
    clarification_candidates: list[ClarificationCandidate] = field(
        default_factory=list
    )

    @property
    def open_questions(self) -> list[str]:
        return [item.question for item in self.clarification_candidates]

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
        raw_questions = payload.get("open_questions")
        if not isinstance(raw_questions, list):
            raise RequirementAnalysisValidationError(
                "open_questions must be a list"
            )
        if len(raw_questions) > 10:
            raise RequirementAnalysisValidationError(
                "open_questions must contain at most 10 candidates"
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
            clarification_candidates=[
                ClarificationCandidate.from_dict(item)
                for item in raw_questions
            ],
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
            "open_questions": [
                item.to_dict() for item in self.clarification_candidates
            ],
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


@dataclass(frozen=True)
class TestPointRevisionOperation:
    action: str
    target_title: str | None = None
    test_point: TestPoint | None = None

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "TestPointRevisionOperation":
        if not isinstance(payload, dict):
            raise TestPointValidationError(
                "each revision operation must be an object"
            )

        action = payload.get("action")
        if action not in {"add", "replace", "remove"}:
            raise TestPointValidationError(
                "revision action must be add, replace, or remove"
            )

        expected_fields = {
            "add": {"action", "test_point"},
            "replace": {"action", "target_title", "test_point"},
            "remove": {"action", "target_title"},
        }[action]
        if set(payload) != expected_fields:
            raise TestPointValidationError(
                f"{action} operation must contain only "
                + ", ".join(sorted(expected_fields))
            )

        target_title = payload.get("target_title")
        if action in {"replace", "remove"}:
            if not isinstance(target_title, str) or not target_title.strip():
                raise TestPointValidationError(
                    "target_title must be a non-empty string"
                )
            target_title = target_title.strip()

        raw_test_point = payload.get("test_point")
        test_point = None
        if action in {"add", "replace"}:
            test_point = TestPoint.from_dict(raw_test_point)

        return cls(
            action=action,
            target_title=target_title,
            test_point=test_point,
        )


@dataclass(frozen=True)
class TestPointRevisionPlan:
    operations: list[TestPointRevisionOperation]

    @classmethod
    def from_json(cls, raw_response: str) -> "TestPointRevisionPlan":
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

        if not isinstance(payload, dict) or set(payload) != {"operations"}:
            raise TestPointValidationError(
                "top-level JSON must contain only operations"
            )
        raw_operations = payload["operations"]
        if not isinstance(raw_operations, list) or not raw_operations:
            raise TestPointValidationError(
                "operations must be a non-empty list"
            )
        if len(raw_operations) > 20:
            raise TestPointValidationError(
                "operations must contain at most 20 items"
            )
        return cls(
            operations=[
                TestPointRevisionOperation.from_dict(item)
                for item in raw_operations
            ]
        )

    def apply_to(
        self,
        current_test_points: list[dict[str, Any]],
    ) -> TestPointGenerationResult:
        original = [
            TestPoint.from_dict(item) for item in current_test_points
        ]
        revised = list(original)

        for operation in self.operations:
            titles = [point.title for point in revised]
            if operation.action == "add":
                if operation.test_point is None:
                    raise TestPointValidationError(
                        "add operation requires test_point"
                    )
                if operation.test_point.title in titles:
                    raise TestPointValidationError(
                        "add operation creates a duplicate title: "
                        + operation.test_point.title
                    )
                revised.append(operation.test_point)
                continue

            if operation.target_title is None:
                raise TestPointValidationError(
                    f"{operation.action} operation requires target_title"
                )
            matches = [
                index
                for index, title in enumerate(titles)
                if title == operation.target_title
            ]
            if len(matches) != 1:
                raise TestPointValidationError(
                    "target_title must match exactly one test point: "
                    + operation.target_title
                )
            target_index = matches[0]

            if operation.action == "remove":
                revised.pop(target_index)
                continue

            if operation.test_point is None:
                raise TestPointValidationError(
                    "replace operation requires test_point"
                )
            duplicate_titles = [
                title
                for index, title in enumerate(titles)
                if index != target_index
                and title == operation.test_point.title
            ]
            if duplicate_titles:
                raise TestPointValidationError(
                    "replace operation creates a duplicate title: "
                    + operation.test_point.title
                )
            revised[target_index] = operation.test_point

        if not revised:
            raise TestPointValidationError(
                "revision must keep at least one test point"
            )
        if revised == original:
            raise TestPointValidationError(
                "revision did not change any test point"
            )
        return TestPointGenerationResult(test_points=revised)
