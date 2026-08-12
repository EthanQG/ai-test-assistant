from collections import Counter
from dataclasses import dataclass
from typing import Any

from .events import AgentStep
from .human_feedback import HumanFeedbackHandler
from .models import TestPoint
from .review_models import TestPointReviewResult
from .state import KnowledgeRetrievalStatus, TestAnalysisState


class FinalizationError(RuntimeError):
    """Raised when a reviewed task cannot be finalized safely."""


@dataclass(frozen=True)
class FinalizationResult:
    requirement_summary: str
    modules: list[str]
    test_point_count: int
    category_counts: dict[str, int]
    priority_counts: dict[str, int]
    source_counts: dict[str, int]
    coverage_summary: dict[str, int]
    quality_summary: dict[str, Any]
    inferred_risks: list[dict[str, str]]
    warnings: list[str]
    test_points: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_summary": self.requirement_summary,
            "modules": list(self.modules),
            "test_point_count": self.test_point_count,
            "category_counts": dict(self.category_counts),
            "priority_counts": dict(self.priority_counts),
            "source_counts": dict(self.source_counts),
            "coverage_summary": dict(self.coverage_summary),
            "quality_summary": dict(self.quality_summary),
            "inferred_risks": [
                dict(risk) for risk in self.inferred_risks
            ],
            "warnings": list(self.warnings),
            "test_points": [
                dict(test_point) for test_point in self.test_points
            ],
        }


class Finalizer:
    """Builds the deterministic final result without changing test points."""

    def finalize(self, state: TestAnalysisState) -> FinalizationResult:
        test_points, review = self._validate_prerequisites(state)
        state.start_step(
            AgentStep.FINALIZE,
            "正在整理最终测试分析结果",
        )

        try:
            result = self._build_result(state, test_points, review)
            report = self._build_markdown(result)
            state.final_result = result.to_dict()
            state.complete_step(
                AgentStep.FINALIZE,
                "最终测试分析结果整理完成",
                {
                    "test_point_count": result.test_point_count,
                    "overall_score": (
                        result.quality_summary["overall_score"]
                    ),
                    "warning_count": len(result.warnings),
                },
            )
            state.complete(report)
            return result
        except Exception as exc:
            state.fail(f"最终结果整理失败: {exc}")
            raise FinalizationError(
                f"finalization failed: {exc}"
            ) from exc

    @staticmethod
    def _validate_prerequisites(
        state: TestAnalysisState,
    ) -> tuple[list[TestPoint], TestPointReviewResult]:
        if state.open_questions:
            raise FinalizationError(
                "open questions must be resolved before finalization"
            )
        if not state.test_points:
            raise FinalizationError(
                "structured test points must exist before finalization"
            )
        if not state.review_result:
            raise FinalizationError(
                "test points must be reviewed before finalization"
            )
        if (
            state.review_passed is not True
            and state.automatic_revision_count < state.max_revision_count
        ):
            raise FinalizationError(
                "failed review can only be finalized after revision limit"
            )
        if HumanFeedbackHandler.ready_feedback(state):
            raise FinalizationError(
                "ready human feedback must be applied before finalization"
            )

        try:
            test_points = [
                TestPoint.from_dict(item) for item in state.test_points
            ]
            review = TestPointReviewResult.from_dict(state.review_result)
        except Exception as exc:
            raise FinalizationError(
                f"finalization input is invalid: {exc}"
            ) from exc
        return test_points, review

    @staticmethod
    def _build_result(
        state: TestAnalysisState,
        test_points: list[TestPoint],
        review: TestPointReviewResult,
    ) -> FinalizationResult:
        category_counts = Counter(
            test_point.category.value for test_point in test_points
        )
        priority_counts = Counter(
            test_point.priority.value for test_point in test_points
        )
        source_counts = Counter(
            source.value
            for test_point in test_points
            for source in test_point.sources
        )
        coverage_counts = Counter(
            item.status for item in review.requirement_coverage
        )
        coverage_summary = {
            "total": len(review.requirement_coverage),
            "covered": coverage_counts["covered"],
            "partial": coverage_counts["partial"],
            "missing": coverage_counts["missing"],
        }
        warnings = Finalizer._warnings(state, review)

        return FinalizationResult(
            requirement_summary=state.requirement_summary,
            modules=list(state.modules),
            test_point_count=len(test_points),
            category_counts=dict(category_counts),
            priority_counts=dict(priority_counts),
            source_counts=dict(source_counts),
            coverage_summary=coverage_summary,
            quality_summary={
                "overall_score": review.overall_score,
                "review_threshold": state.review_threshold,
                "review_passed": state.review_passed is True,
                "dimension_scores": review.dimension_scores.to_dict(),
                "review_rounds": len(state.review_history),
                "revision_count": state.revision_count,
                "automatic_revision_count": (
                    state.automatic_revision_count
                ),
                "human_revision_count": state.human_revision_count,
            },
            inferred_risks=[
                dict(risk) for risk in state.inferred_risks
            ],
            warnings=warnings,
            test_points=[
                test_point.to_dict() for test_point in test_points
            ],
        )

    @staticmethod
    def _warnings(
        state: TestAnalysisState,
        review: TestPointReviewResult,
    ) -> list[str]:
        warnings = []
        if state.review_passed is not True:
            warnings.append(
                "Reviewer评分未达到推荐质量门槛；报告保留未解决问题，可提交人工反馈后生成新版"
            )
        if (
            state.knowledge_retrieval_status
            == KnowledgeRetrievalStatus.DEGRADED
        ):
            detail = state.rag_error_message or "未知原因"
            warnings.append(f"历史知识检索已降级：{detail}")
        elif (
            state.knowledge_retrieval_status
            == KnowledgeRetrievalStatus.NO_MATCH
        ):
            warnings.append("未命中可复用的历史测试资产")

        warnings.extend(
            f"评审仍建议关注：{scenario}"
            for scenario in review.missing_scenarios
        )
        warnings.extend(
            f"用户暂未确认：{question}"
            for question in state.deferred_questions
        )
        return warnings

    @staticmethod
    def _build_markdown(result: FinalizationResult) -> str:
        lines = [
            "# 测试分析报告",
            "",
            "## 需求概述",
            "",
            result.requirement_summary,
            "",
            "## 质量概览",
            "",
            f"- 测试点数量：{result.test_point_count}",
            (
                "- Reviewer评分："
                f"{result.quality_summary['overall_score']}"
                f"/100（阈值 {result.quality_summary['review_threshold']}）"
            ),
            (
                "- 需求覆盖："
                f"{result.coverage_summary['covered']}"
                f"/{result.coverage_summary['total']}"
            ),
            (
                "- 自动修正次数："
                f"{result.quality_summary['automatic_revision_count']}"
            ),
            (
                "- 人工反馈修正次数："
                f"{result.quality_summary['human_revision_count']}"
            ),
            "",
            "## 结构化测试点",
            "",
            (
                "| 序号 | 标题 | 分类 | 优先级 | 场景 | 前置条件 | "
                "执行步骤 | 预期结果 | 来源 | 来源依据 |"
            ),
            "|---:|---|---|---|---|---|---|---|---|---|",
        ]
        for index, test_point in enumerate(result.test_points, start=1):
            category = {
                "functional": "功能",
                "boundary": "边界",
                "exception": "异常",
                "non_functional": "非功能",
            }.get(test_point["category"], test_point["category"])
            cells = [
                str(index),
                test_point["title"],
                category,
                test_point["priority"],
                test_point["scenario"],
                "<br>".join(test_point["preconditions"]),
                "<br>".join(test_point["steps"]),
                "<br>".join(test_point["expected_results"]),
                "、".join(test_point["sources"]),
                "<br>".join(test_point["source_refs"]),
            ]
            lines.append(
                "| " + " | ".join(
                    Finalizer._markdown_table_cell(cell)
                    for cell in cells
                ) + " |"
            )
        lines.append("")

        if result.inferred_risks:
            lines.extend(["## 推导风险", ""])
            for risk in result.inferred_risks:
                lines.append(
                    f"- {risk['risk']}（依据：{risk['basis']}）"
                )
            lines.append("")

        if result.warnings:
            lines.extend(["## 注意事项", ""])
            lines.extend(f"- {warning}" for warning in result.warnings)
            lines.append("")

        return "\n".join(lines).strip()

    @staticmethod
    def _markdown_table_cell(value: Any) -> str:
        return str(value).replace("|", r"\|").replace("\n", "<br>")
