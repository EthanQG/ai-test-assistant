from services.llm_service import LLMService
from services.prompt_service import PromptService

from .events import AgentStep
from .review_models import TestPointReviewResult
from .state import TestAnalysisState
from .structured_output import generate_and_parse_json


class TestPointReviewError(RuntimeError):
    """Raised when the test point review node cannot complete."""


class TestPointReviewer:
    """Reviews structured test points and stores a validated quality result."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_service: PromptService | None = None,
        passing_score: int = 80,
    ):
        if not 0 <= passing_score <= 100:
            raise ValueError("passing_score must be between 0 and 100")
        self.llm_service = llm_service or LLMService()
        self.prompt_service = prompt_service or PromptService()
        self.passing_score = passing_score

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
            user_prompt = self.prompt_service.build_test_point_review_prompt(
                self._requirement_analysis_payload(state),
                state.test_points,
            )
            result = generate_and_parse_json(
                self.llm_service,
                user_prompt,
                system_prompt,
                TestPointReviewResult.from_json,
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

    @staticmethod
    def _requirement_analysis_payload(
        state: TestAnalysisState,
    ) -> dict:
        return {
            "summary": state.requirement_summary,
            "modules": list(state.modules),
            "requirement_facts": list(state.requirement_facts),
            "business_rules": list(state.business_rules),
            "state_transitions": list(state.state_transitions),
            "inferred_risks": list(state.inferred_risks),
        }
