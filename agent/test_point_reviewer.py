from dataclasses import replace

from services.llm_service import LLMService
from services.prompt_service import PromptService

from .events import AgentStep
from .context_builder import ContextBuilder
from .review_models import TestPointReviewResult
from .state import TestAnalysisState
from .structured_output import (
    generate_and_parse_json,
)


REVIEW_STRUCTURED_OUTPUT_MAX_TOKENS = 16_384


class TestPointReviewError(RuntimeError):
    """Raised when the test point review node cannot complete."""


class TestPointReviewer:
    """Reviews structured test points and stores a validated quality result."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_service: PromptService | None = None,
        passing_score: int = 80,
        context_builder: ContextBuilder | None = None,
    ):
        if not 0 <= passing_score <= 100:
            raise ValueError("passing_score must be between 0 and 100")
        self.llm_service = llm_service or LLMService()
        self.prompt_service = prompt_service or PromptService()
        self.passing_score = passing_score
        self.context_builder = context_builder or ContextBuilder()

    def review(self, state: TestAnalysisState) -> TestPointReviewResult:
        self._validate_prerequisites(state)
        state.start_step(
            AgentStep.REVIEW_TEST_POINTS,
            "正在评审结构化测试点质量",
        )

        try:
            system_prompt = self.prompt_service.load_system_prompt(
                "test_point_review"
            )
            context = self.context_builder.build_test_point_review(state)
            user_prompt = self.prompt_service.build_test_point_review_prompt(
                context.values["requirement_analysis"],
                context.values["test_points"],
            )
            fact_by_id = {
                f"F{index:03d}": fact
                for index, fact in enumerate(
                    state.requirement_facts,
                    start=1,
                )
            }
            result = self._generate_review(
                user_prompt,
                system_prompt,
                fact_by_id,
            )
            self._validate_coverage(state, result)
            passed = self._is_passing(result)

            state.review_result = result.to_dict()
            state.review_passed = passed
            state.review_threshold = self.passing_score
            state.review_history.append(
                {
                    "review_round": len(state.review_history) + 1,
                    "revision_count": state.revision_count,
                    "automatic_revision_count": (
                        state.automatic_revision_count
                    ),
                    "human_revision_count": state.human_revision_count,
                    "passed": passed,
                    "result": result.to_dict(),
                }
            )
            state.complete_step(
                AgentStep.REVIEW_TEST_POINTS,
                "结构化测试点质量评审完成",
                {
                    "overall_score": result.overall_score,
                    "passing_score": self.passing_score,
                    "passed": passed,
                    "missing_requirement_count": (
                        result.missing_requirement_count
                    ),
                    "uncovered_requirement_count": (
                        result.uncovered_requirement_count
                    ),
                    "missing_scenario_count": len(
                        result.missing_scenarios
                    ),
                    "duplicate_group_count": len(
                        result.duplicate_groups
                    ),
                    "hallucination_issue_count": len(
                        result.hallucination_issues
                    ),
                    "context_metrics": context.metrics.to_dict(),
                },
            )
            return result
        except Exception as exc:
            state.fail(f"测试点评审失败: {exc}")
            raise TestPointReviewError(
                f"test point review failed: {exc}"
            ) from exc

    def _is_passing(self, result: TestPointReviewResult) -> bool:
        return (
            result.overall_score >= self.passing_score
            and result.uncovered_requirement_count == 0
            and not result.hallucination_issues
        )

    def _generate_review(
        self,
        user_prompt: str,
        system_prompt: str,
        fact_by_id: dict[str, str],
    ) -> TestPointReviewResult:
        parser = lambda raw: self._parse_result(raw, fact_by_id)
        try:
            return generate_and_parse_json(
                self.llm_service,
                user_prompt,
                system_prompt,
                parser,
                max_tokens=REVIEW_STRUCTURED_OUTPUT_MAX_TOKENS,
            )
        except ValueError as exc:
            if "max_tokens" not in str(exc):
                raise
            compact_retry_prompt = (
                user_prompt
                + "\n\n上一次评审输出因长度限制被截断。"
                "请只返回完整紧凑JSON；coverage只写fact_id，"
                "问题和建议只保留影响修正的主要项，不得复述输入。"
            )
            return generate_and_parse_json(
                self.llm_service,
                compact_retry_prompt,
                system_prompt,
                parser,
                max_attempts=1,
                max_tokens=REVIEW_STRUCTURED_OUTPUT_MAX_TOKENS,
            )

    @staticmethod
    def _parse_result(
        raw_response: str,
        fact_by_id: dict[str, str],
    ) -> TestPointReviewResult:
        result = TestPointReviewResult.from_json(raw_response)
        return replace(
            result,
            requirement_coverage=[
                replace(
                    item,
                    requirement_fact=fact_by_id.get(
                        item.requirement_fact,
                        item.requirement_fact,
                    ),
                )
                for item in result.requirement_coverage
            ],
        )

    @staticmethod
    def _validate_coverage(
        state: TestAnalysisState,
        result: TestPointReviewResult,
    ) -> None:
        expected_facts = set(state.requirement_facts)
        reviewed_facts = [
            item.requirement_fact
            for item in result.requirement_coverage
        ]
        if len(reviewed_facts) != len(set(reviewed_facts)):
            raise ValueError(
                "requirement coverage contains duplicate facts"
            )
        if set(reviewed_facts) != expected_facts:
            raise ValueError(
                "requirement coverage must evaluate every requirement fact"
            )

    @staticmethod
    def _validate_prerequisites(state: TestAnalysisState) -> None:
        if not state.requirement_facts:
            raise TestPointReviewError(
                "requirement analysis must be completed first"
            )
        if not state.test_points:
            raise TestPointReviewError(
                "structured test points must be generated first"
            )
