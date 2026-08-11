from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .models import (
    ClarificationCandidate,
    ClarificationCategory,
    InferredRisk,
    RequirementAnalysisResult,
    RequirementAnalysisValidationError,
)
from .requirement_statements import RequirementStatement


def _text(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RequirementAnalysisValidationError(
            f"{name} must be a non-empty string"
        )
    return value.strip()


def _strings(payload: dict[str, Any], name: str) -> list[str]:
    value = payload.get(name)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise RequirementAnalysisValidationError(
            f"{name} must contain strings"
        )
    return [item.strip() for item in value]


def _payload(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        raise RequirementAnalysisValidationError(
            f"compact response is not valid JSON: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise RequirementAnalysisValidationError(
            "compact response must be an object"
        )
    return value


@dataclass(frozen=True)
class CompactRisk:
    risk: str
    basis_ids: tuple[str, ...]


@dataclass(frozen=True)
class CompactRequirementBatch:
    summary: str
    modules: tuple[str, ...]
    fact_ids: tuple[str, ...]
    business_rule_ids: tuple[str, ...]
    state_transition_ids: tuple[str, ...]
    risks: tuple[CompactRisk, ...]

    @classmethod
    def from_json(
        cls,
        raw: str,
        allowed_ids: set[str],
    ) -> "CompactRequirementBatch":
        payload = _payload(raw)
        expected = {
            "summary", "modules", "fact_ids", "business_rule_ids",
            "state_transition_ids", "inferred_risks",
        }
        if set(payload) != expected:
            raise RequirementAnalysisValidationError(
                "compact requirement fields are invalid"
            )
        risks = payload["inferred_risks"]
        if not isinstance(risks, list):
            raise RequirementAnalysisValidationError(
                "inferred_risks must be a list"
            )
        result = cls(
            summary=_text(payload, "summary"),
            modules=tuple(_strings(payload, "modules")),
            fact_ids=tuple(_strings(payload, "fact_ids")),
            business_rule_ids=tuple(_strings(payload, "business_rule_ids")),
            state_transition_ids=tuple(
                _strings(payload, "state_transition_ids")
            ),
            risks=tuple(cls._risk(item) for item in risks),
        )
        referenced = {
            *result.fact_ids,
            *result.business_rule_ids,
            *result.state_transition_ids,
            *(item for risk in result.risks for item in risk.basis_ids),
        }
        unknown = referenced - allowed_ids
        if unknown:
            raise RequirementAnalysisValidationError(
                "compact response references unknown statement IDs: "
                + ", ".join(sorted(unknown))
            )
        return result

    @staticmethod
    def _risk(payload: Any) -> CompactRisk:
        if not isinstance(payload, dict) or set(payload) != {
            "risk", "basis_ids"
        }:
            raise RequirementAnalysisValidationError(
                "compact risk fields are invalid"
            )
        basis_ids = _strings(payload, "basis_ids")
        if not basis_ids:
            raise RequirementAnalysisValidationError(
                "compact risk requires basis_ids"
            )
        return CompactRisk(_text(payload, "risk"), tuple(basis_ids))

    def to_requirement_result(
        self,
        catalog: dict[str, RequirementStatement],
    ) -> RequirementAnalysisResult:
        def texts(ids: tuple[str, ...]) -> list[str]:
            return [catalog[item].text for item in ids]

        return RequirementAnalysisResult(
            summary=self.summary,
            modules=list(self.modules),
            requirement_facts=texts(self.fact_ids),
            business_rules=texts(self.business_rule_ids),
            state_transitions=texts(self.state_transition_ids),
            inferred_risks=[
                InferredRisk(
                    risk=item.risk,
                    basis="；".join(
                        f"[{statement_id}｜{catalog[statement_id].section}] "
                        f"{catalog[statement_id].text}"
                        for statement_id in item.basis_ids
                    ),
                )
                for item in self.risks
            ],
            clarification_candidates=[],
        )


@dataclass(frozen=True)
class CompactGlobalQuestions:
    candidates: tuple[ClarificationCandidate, ...]

    @classmethod
    def from_json(
        cls,
        raw: str,
        catalog: dict[str, RequirementStatement],
    ) -> "CompactGlobalQuestions":
        payload = _payload(raw)
        if set(payload) != {"open_questions"}:
            raise RequirementAnalysisValidationError(
                "global question fields are invalid"
            )
        questions = payload["open_questions"]
        if not isinstance(questions, list) or len(questions) > 10:
            raise RequirementAnalysisValidationError(
                "open_questions must be a list with at most 10 items"
            )
        candidates = []
        for item in questions:
            if not isinstance(item, dict) or set(item) != {
                "question", "category", "blocking_reason", "evidence_ids"
            }:
                raise RequirementAnalysisValidationError(
                    "compact question fields are invalid"
                )
            evidence_ids = _strings(item, "evidence_ids")
            unknown = set(evidence_ids) - set(catalog)
            if not evidence_ids or unknown:
                raise RequirementAnalysisValidationError(
                    "compact question evidence IDs are invalid"
                )
            try:
                category = ClarificationCategory(_text(item, "category"))
            except ValueError as exc:
                raise RequirementAnalysisValidationError(
                    "open question category is unsupported"
                ) from exc
            evidence = "；".join(
                f"[{statement_id}｜{catalog[statement_id].section}] "
                f"{catalog[statement_id].text}"
                for statement_id in evidence_ids
            )
            candidates.append(
                ClarificationCandidate(
                    question=_text(item, "question"),
                    category=category,
                    blocking_reason=_text(item, "blocking_reason"),
                    evidence=evidence,
                )
            )
        return cls(tuple(candidates))

