from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
import json
import math
import re
from typing import Any

from utils.telemetry import MetricErrorCategory, observed_service_call

from .state import TestAnalysisState


class ContextBuildError(ValueError):
    """Raised when protected node input cannot fit its explicit budget."""


class ContextNode(str, Enum):
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    TEST_POINT_GENERATION = "test_point_generation"
    TEST_POINT_REVIEW = "test_point_review"
    TEST_POINT_REVISION = "test_point_revision"


@dataclass(frozen=True)
class ContextMetrics:
    node: ContextNode
    original_chars: int
    final_chars: int
    estimated_input_tokens: int
    input_token_budget: int
    truncated_sections: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node.value,
            "original_chars": self.original_chars,
            "final_chars": self.final_chars,
            "estimated_input_tokens": self.estimated_input_tokens,
            "input_token_budget": self.input_token_budget,
            "truncated_sections": list(self.truncated_sections),
        }


@dataclass(frozen=True)
class BuiltContext:
    values: dict[str, Any]
    metrics: ContextMetrics


_MODEL_CONTEXT_LIMIT = 64_000
_SAFETY_MARGIN_TOKENS = 4_096
_OUTPUT_TOKEN_RESERVES = {
    ContextNode.REQUIREMENT_ANALYSIS: 8_192,
    ContextNode.KNOWLEDGE_RETRIEVAL: 0,
    ContextNode.TEST_POINT_GENERATION: 8_192,
    ContextNode.TEST_POINT_REVIEW: 8_192,
    ContextNode.TEST_POINT_REVISION: 8_192,
}
_INPUT_POLICY_CAPS = {
    ContextNode.REQUIREMENT_ANALYSIS: 16_000,
    ContextNode.KNOWLEDGE_RETRIEVAL: 4_000,
    ContextNode.TEST_POINT_GENERATION: 20_000,
    ContextNode.TEST_POINT_REVIEW: 40_000,
    ContextNode.TEST_POINT_REVISION: 42_000,
}


class ContextBuilder:
    """Build minimal, bounded, node-specific context from AgentState."""

    MODEL_CONTEXT_LIMIT = _MODEL_CONTEXT_LIMIT
    SAFETY_MARGIN_TOKENS = _SAFETY_MARGIN_TOKENS
    OUTPUT_TOKEN_RESERVES = _OUTPUT_TOKEN_RESERVES
    INPUT_POLICY_CAPS = _INPUT_POLICY_CAPS
    INPUT_TOKEN_BUDGETS = {
        node: min(
            policy_cap,
            _MODEL_CONTEXT_LIMIT
            - _OUTPUT_TOKEN_RESERVES[node]
            - _SAFETY_MARGIN_TOKENS,
        )
        for node, policy_cap in _INPUT_POLICY_CAPS.items()
    }
    SECTION_CHAR_LIMITS = {
        "requirement": 24_000,
        "retrieval_requirement": 10_000,
        "local_bug_knowledge": 4_000,
        "rag_context": 8_000,
    }
    _IMPORTANT_HINTS = (
        "规则",
        "必须",
        "不得",
        "允许",
        "上限",
        "下限",
        "金额",
        "次数",
        "时限",
        "超时",
        "状态",
        "成功",
        "失败",
        "退款",
        "权限",
        "重试",
        "幂等",
        "来源",
        "asset_id",
        "source",
        "ocr",
        "视觉",
    )
    _TRUNCATION_MARKER = "[上下文已按节点预算裁剪]"

    @observed_service_call(
        operation="build_requirement_analysis_context",
        dependency="context_builder",
        error_category=MetricErrorCategory.INPUT_BUDGET,
    )
    def build_requirement_analysis(self, state: TestAnalysisState) -> BuiltContext:
        requirement, truncated = self._fit_text(
            state.requirement,
            self.SECTION_CHAR_LIMITS["requirement"],
        )
        values = {
            "requirement": requirement,
            "user_clarifications": deepcopy(state.user_clarifications),
            "deferred_questions": list(state.deferred_questions),
        }
        return self._result(
            ContextNode.REQUIREMENT_ANALYSIS,
            values,
            original_values={**values, "requirement": state.requirement},
            truncated_sections=("requirement",) if truncated else (),
        )

    @observed_service_call(
        operation="build_knowledge_retrieval_context",
        dependency="context_builder",
        error_category=MetricErrorCategory.INPUT_BUDGET,
    )
    def build_knowledge_retrieval(self, state: TestAnalysisState) -> BuiltContext:
        requirement, truncated = self._fit_text(
            state.requirement,
            self.SECTION_CHAR_LIMITS["retrieval_requirement"],
        )
        values = {
            "requirement": requirement,
            "requirement_summary": state.requirement_summary,
            "modules": list(state.modules),
            "requirement_facts": list(state.requirement_facts),
            "business_rules": list(state.business_rules),
            "state_transitions": list(state.state_transitions),
            "inferred_risks": deepcopy(state.inferred_risks),
        }
        return self._result(
            ContextNode.KNOWLEDGE_RETRIEVAL,
            values,
            original_values={**values, "requirement": state.requirement},
            truncated_sections=("requirement",) if truncated else (),
        )

    @observed_service_call(
        operation="build_test_point_generation_context",
        dependency="context_builder",
        error_category=MetricErrorCategory.INPUT_BUDGET,
    )
    def build_test_point_generation(self, state: TestAnalysisState) -> BuiltContext:
        local_knowledge, local_truncated = self._fit_text(
            state.local_bug_knowledge,
            self.SECTION_CHAR_LIMITS["local_bug_knowledge"],
        )
        rag_context, rag_truncated = self._fit_text(
            state.rag_context,
            self.SECTION_CHAR_LIMITS["rag_context"],
        )
        values = {
            "requirement_analysis": self.requirement_analysis_payload(state),
            "local_bug_knowledge": local_knowledge,
            "rag_context": rag_context,
        }
        truncated_sections = []
        if local_truncated:
            truncated_sections.append("local_bug_knowledge")
        if rag_truncated:
            truncated_sections.append("rag_context")
        return self._result(
            ContextNode.TEST_POINT_GENERATION,
            values,
            original_values={
                **values,
                "local_bug_knowledge": state.local_bug_knowledge,
                "rag_context": state.rag_context,
            },
            truncated_sections=tuple(truncated_sections),
        )

    @observed_service_call(
        operation="build_test_point_review_context",
        dependency="context_builder",
        error_category=MetricErrorCategory.INPUT_BUDGET,
    )
    def build_test_point_review(self, state: TestAnalysisState) -> BuiltContext:
        values = {
            "requirement_analysis": self.requirement_analysis_payload(state),
            "test_points": deepcopy(state.test_points),
        }
        return self._result(ContextNode.TEST_POINT_REVIEW, values)

    @observed_service_call(
        operation="build_test_point_revision_context",
        dependency="context_builder",
        error_category=MetricErrorCategory.INPUT_BUDGET,
    )
    def build_test_point_revision(
        self,
        state: TestAnalysisState,
        *,
        review_result: dict[str, Any] | None,
        human_feedback: list[dict[str, Any]],
    ) -> BuiltContext:
        values = {
            "requirement_analysis": self.requirement_analysis_payload(state),
            "test_points": deepcopy(state.test_points),
            "review_result": deepcopy(review_result),
            "human_feedback": deepcopy(human_feedback),
        }
        return self._result(ContextNode.TEST_POINT_REVISION, values)

    @staticmethod
    def requirement_analysis_payload(state: TestAnalysisState) -> dict[str, Any]:
        return {
            "summary": state.requirement_summary,
            "modules": list(state.modules),
            "requirement_facts": list(state.requirement_facts),
            "business_rules": list(state.business_rules),
            "state_transitions": list(state.state_transitions),
            "inferred_risks": deepcopy(state.inferred_risks),
            "user_clarifications": deepcopy(state.user_clarifications),
            "deferred_questions": list(state.deferred_questions),
        }

    def _result(
        self,
        node: ContextNode,
        values: dict[str, Any],
        *,
        original_values: dict[str, Any] | None = None,
        truncated_sections: tuple[str, ...] = (),
    ) -> BuiltContext:
        original_chars = self._serialized_chars(original_values or values)
        final_chars = self._serialized_chars(values)
        estimated_tokens = self.estimate_tokens(
            json.dumps(values, ensure_ascii=False, separators=(",", ":"))
        )
        budget = self.INPUT_TOKEN_BUDGETS[node]
        if estimated_tokens > budget:
            raise ContextBuildError(
                f"{node.value} protected context exceeds input token budget: "
                f"{estimated_tokens} > {budget}"
            )
        return BuiltContext(
            values=values,
            metrics=ContextMetrics(
                node=node,
                original_chars=original_chars,
                final_chars=final_chars,
                estimated_input_tokens=estimated_tokens,
                input_token_budget=budget,
                truncated_sections=truncated_sections,
            ),
        )

    @classmethod
    def _fit_text(cls, text: str, max_chars: int) -> tuple[str, bool]:
        cleaned = text.strip()
        if len(cleaned) <= max_chars:
            return cleaned, False
        chunks = cls._chunks(cleaned)
        selected: list[int] = []
        used = len(cls._TRUNCATION_MARKER) + 2

        def add(index: int) -> None:
            nonlocal used
            if index in selected:
                return
            chunk = chunks[index]
            cost = len(chunk) + 1
            if used + cost <= max_chars:
                selected.append(index)
                used += cost

        for index, chunk in enumerate(chunks):
            if cls._is_important(chunk):
                add(index)
        for index in range(len(chunks)):
            add(index)
        selected.sort()
        result = "\n".join(chunks[index] for index in selected)
        return f"{result}\n{cls._TRUNCATION_MARKER}", True

    @staticmethod
    def _chunks(text: str, size: int = 500) -> list[str]:
        chunks: list[str] = []
        for line in text.splitlines() or [text]:
            cleaned = line.strip()
            if not cleaned:
                continue
            chunks.extend(
                cleaned[index : index + size]
                for index in range(0, len(cleaned), size)
            )
        return chunks

    @classmethod
    def _is_important(cls, text: str) -> bool:
        normalized = text.casefold()
        return bool(re.search(r"\d", text)) or any(
            hint.casefold() in normalized for hint in cls._IMPORTANT_HINTS
        )

    @staticmethod
    def estimate_tokens(text: str) -> int:
        cjk_count = len(re.findall(r"[\u3400-\u9fff]", text))
        non_cjk = len(re.sub(r"[\u3400-\u9fff\s]", "", text))
        return cjk_count + math.ceil(non_cjk / 4)

    @staticmethod
    def _serialized_chars(values: dict[str, Any]) -> int:
        return len(json.dumps(values, ensure_ascii=False))
