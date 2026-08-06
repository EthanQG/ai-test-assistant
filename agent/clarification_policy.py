from __future__ import annotations

from dataclasses import dataclass
import re

from .models import (
    ClarificationCandidate,
    ClarificationCategory,
    InferredRisk,
)


@dataclass(frozen=True)
class ClarificationSelection:
    blocking: tuple[ClarificationCandidate, ...]
    non_blocking_risks: tuple[InferredRisk, ...]


class ClarificationQuestionPolicy:
    """Deterministically limits which LLM candidates may pause a task."""

    MAX_BLOCKING_QUESTIONS = 3
    BLOCKING_CATEGORIES = {
        ClarificationCategory.CORE_RULE,
        ClarificationCategory.CRITICAL_VALUE,
        ClarificationCategory.FLOW_BRANCH,
        ClarificationCategory.REQUIREMENT_CONFLICT,
    }
    NON_BLOCKING_TEXT_HINTS = (
        "数据库",
        "表结构",
        "缓存结构",
        "redis",
        "消息队列",
        "线程",
        "技术栈",
        "部署方式",
        "sql",
        "索引类型",
        "按钮颜色",
        "字体",
        "标点",
        "动画",
        "圆角",
        "阴影",
    )

    def select(
        self,
        candidates: list[ClarificationCandidate],
        *,
        deferred_questions: list[str] | None = None,
    ) -> ClarificationSelection:
        deferred = {
            self._normalize(question)
            for question in (deferred_questions or [])
        }
        seen: set[str] = set()
        blocking: list[ClarificationCandidate] = []
        risks: list[InferredRisk] = []

        for candidate in candidates:
            normalized = self._normalize(candidate.question)
            if not normalized or normalized in seen or normalized in deferred:
                continue
            seen.add(normalized)
            if (
                candidate.category in self.BLOCKING_CATEGORIES
                and not self._has_non_blocking_hint(candidate.question)
                and len(blocking) < self.MAX_BLOCKING_QUESTIONS
            ):
                blocking.append(candidate)
                continue
            risks.append(
                InferredRisk(
                    risk=f"未阻塞任务的待确认事项：{candidate.question}",
                    basis=candidate.evidence,
                )
            )

        return ClarificationSelection(
            blocking=tuple(blocking),
            non_blocking_risks=tuple(risks),
        )

    @staticmethod
    def _normalize(question: str) -> str:
        return re.sub(r"[\s？?。！!，,；;：:]", "", question).casefold()

    @classmethod
    def _has_non_blocking_hint(cls, question: str) -> bool:
        normalized = question.casefold()
        return any(
            hint.casefold() in normalized
            for hint in cls.NON_BLOCKING_TEXT_HINTS
        )
