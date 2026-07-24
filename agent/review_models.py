import json
from dataclasses import dataclass, field
from typing import Any

from .models import RequirementAnalysisResult


class TestPointReviewValidationError(ValueError):
    """Raised when an LLM review response violates the review contract."""


def _required_text(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise TestPointReviewValidationError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()


def _string_list(
    payload: dict[str, Any],
    field_name: str,
) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise TestPointReviewValidationError(
            f"{field_name} must be a list"
        )
    cleaned = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise TestPointReviewValidationError(
                f"{field_name} must contain non-empty strings"
            )
        cleaned.append(item.strip())
    return cleaned


def _score(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TestPointReviewValidationError(
            f"{field_name} must be an integer"
        )
    if not 0 <= value <= 100:
        raise TestPointReviewValidationError(
            f"{field_name} must be between 0 and 100"
        )
    return value


@dataclass(frozen=True)
class ReviewDimensionScores:
    requirement_coverage: int
    boundary_exception: int
    executability: int
    traceability: int

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReviewDimensionScores":
        if not isinstance(payload, dict):
            raise TestPointReviewValidationError(
                "dimension_scores must be an object"
            )
        expected_fields = {
            "requirement_coverage",
            "boundary_exception",
            "executability",
            "traceability",
        }
        if set(payload) != expected_fields:
            raise TestPointReviewValidationError(
                "dimension_scores fields are invalid"
            )
        return cls(
            requirement_coverage=_score(
                payload,
                "requirement_coverage",
            ),
            boundary_exception=_score(
                payload,
                "boundary_exception",
            ),
            executability=_score(payload, "executability"),
            traceability=_score(payload, "traceability"),
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "requirement_coverage": self.requirement_coverage,
            "boundary_exception": self.boundary_exception,
            "executability": self.executability,
            "traceability": self.traceability,
        }


@dataclass(frozen=True)
class RequirementCoverage:
    requirement_fact: str
    status: str
    covered_by: list[str] = field(default_factory=list)
    gap: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RequirementCoverage":
        if not isinstance(payload, dict):
            raise TestPointReviewValidationError(
                "each requirement coverage item must be an object"
            )
        expected_fields = {
            "requirement_fact",
            "status",
            "covered_by",
            "gap",
        }
        if set(payload) != expected_fields:
            raise TestPointReviewValidationError(
                "requirement coverage fields are invalid"
            )
        status = _required_text(payload, "status")
        if status not in {"covered", "partial", "missing"}:
            raise TestPointReviewValidationError(
                "coverage status must be covered, partial, or missing"
            )
        gap = payload.get("gap")
        if not isinstance(gap, str):
            raise TestPointReviewValidationError(
                "gap must be a string"
            )
        return cls(
            requirement_fact=_required_text(
                payload,
                "requirement_fact",
            ),
            status=status,
            covered_by=_string_list(payload, "covered_by"),
            gap=gap.strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_fact": self.requirement_fact,
            "status": self.status,
            "covered_by": list(self.covered_by),
            "gap": self.gap,
        }


@dataclass(frozen=True)
class HallucinationIssue:
    test_point_title: str
    issue: str
    unsupported_claim: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HallucinationIssue":
        if not isinstance(payload, dict):
            raise TestPointReviewValidationError(
                "each hallucination issue must be an object"
            )
        expected_fields = {
            "test_point_title",
            "issue",
            "unsupported_claim",
        }
        if set(payload) != expected_fields:
            raise TestPointReviewValidationError(
                "hallucination issue fields are invalid"
            )
        return cls(
            test_point_title=_required_text(
                payload,
                "test_point_title",
            ),
            issue=_required_text(payload, "issue"),
            unsupported_claim=_required_text(
                payload,
                "unsupported_claim",
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "test_point_title": self.test_point_title,
            "issue": self.issue,
            "unsupported_claim": self.unsupported_claim,
        }


@dataclass(frozen=True)
class TestPointReviewResult:
    overall_score: int
    dimension_scores: ReviewDimensionScores
    requirement_coverage: list[RequirementCoverage]
    missing_scenarios: list[str]
    duplicate_groups: list[list[str]]
    hallucination_issues: list[HallucinationIssue]
    revision_suggestions: list[str]

    @classmethod
    def from_json(cls, raw_response: str) -> "TestPointReviewResult":
        cleaned = RequirementAnalysisResult._strip_code_fence(raw_response)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise TestPointReviewValidationError(
                f"LLM response is not valid JSON: {exc.msg}"
            ) from exc
        if not isinstance(payload, dict):
            raise TestPointReviewValidationError(
                "LLM response must be a JSON object"
            )
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TestPointReviewResult":
        expected_fields = {
            "overall_score",
            "dimension_scores",
            "requirement_coverage",
            "missing_scenarios",
            "duplicate_groups",
            "hallucination_issues",
            "revision_suggestions",
        }
        if set(payload) != expected_fields:
            raise TestPointReviewValidationError(
                "review result fields are invalid"
            )

        raw_coverage = payload["requirement_coverage"]
        if not isinstance(raw_coverage, list):
            raise TestPointReviewValidationError(
                "requirement_coverage must be a list"
            )

        raw_duplicates = payload["duplicate_groups"]
        if not isinstance(raw_duplicates, list):
            raise TestPointReviewValidationError(
                "duplicate_groups must be a list"
            )
        duplicate_groups = []
        for group in raw_duplicates:
            wrapper = {"group": group}
            cleaned_group = _string_list(wrapper, "group")
            if len(cleaned_group) < 2:
                raise TestPointReviewValidationError(
                    "each duplicate group must contain at least two titles"
                )
            duplicate_groups.append(cleaned_group)

        raw_hallucinations = payload["hallucination_issues"]
        if not isinstance(raw_hallucinations, list):
            raise TestPointReviewValidationError(
                "hallucination_issues must be a list"
            )

        return cls(
            overall_score=_score(payload, "overall_score"),
            dimension_scores=ReviewDimensionScores.from_dict(
                payload["dimension_scores"]
            ),
            requirement_coverage=[
                RequirementCoverage.from_dict(item)
                for item in raw_coverage
            ],
            missing_scenarios=_string_list(
                payload,
                "missing_scenarios",
            ),
            duplicate_groups=duplicate_groups,
            hallucination_issues=[
                HallucinationIssue.from_dict(item)
                for item in raw_hallucinations
            ],
            revision_suggestions=_string_list(
                payload,
                "revision_suggestions",
            ),
        )

    @property
    def missing_requirement_count(self) -> int:
        return sum(
            item.status == "missing"
            for item in self.requirement_coverage
        )

    @property
    def uncovered_requirement_count(self) -> int:
        return sum(
            item.status != "covered"
            for item in self.requirement_coverage
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores.to_dict(),
            "requirement_coverage": [
                item.to_dict() for item in self.requirement_coverage
            ],
            "missing_scenarios": list(self.missing_scenarios),
            "duplicate_groups": [
                list(group) for group in self.duplicate_groups
            ],
            "hallucination_issues": [
                item.to_dict() for item in self.hallucination_issues
            ],
            "revision_suggestions": list(self.revision_suggestions),
        }
