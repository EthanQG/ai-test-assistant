from services.llm_service import LLMService
from services.prompt_service import PromptService

from .events import AgentStep
from .models import TestPointGenerationResult
from .state import TestAnalysisState


class TestPointRevisionError(RuntimeError):
    """Raised when the test point revision node cannot complete."""


class TestPointReviser:
    """Revises test points using validated Reviewer feedback."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_service: PromptService | None = None,
    ):
        self.llm_service = llm_service or LLMService()
        self.prompt_service = prompt_service or PromptService()

    def revise(
        self,
        state: TestAnalysisState,
    ) -> TestPointGenerationResult:
        self._validate_prerequisites(state)
        state.start_step(
            AgentStep.REVISE_TEST_POINTS,
            "正在根据评审结果定向修正测试点",
        )

        try:
            original_test_points = list(state.test_points)
            system_prompt = self.prompt_service.load_system_prompt(
                "test_point_revision"
            )
            user_prompt = (
                self.prompt_service.build_test_point_revision_prompt(
                    self._requirement_analysis_payload(state),
                    original_test_points,
                    state.review_result or {},
                )
            )
            raw_response = self.llm_service.generate(
                user_prompt,
                system_prompt,
            )
            result = TestPointGenerationResult.from_json(raw_response)
            revised_test_points = [
                test_point.to_dict()
                for test_point in result.test_points
            ]
            if revised_test_points == original_test_points:
                raise ValueError(
                    "revision did not change any test point"
                )

            state.test_points = revised_test_points
            state.revision_count += 1
            state.review_passed = None
            state.complete_step(
                AgentStep.REVISE_TEST_POINTS,
                "测试点定向修正完成，等待重新评审",
                {
                    "revision_count": state.revision_count,
                    "before_count": len(original_test_points),
                    "after_count": len(revised_test_points),
                    "previous_review_score": (
                        state.review_result or {}
                    ).get("overall_score"),
                    "review_invalidated": True,
                },
            )
            return result
        except Exception as exc:
            state.fail(f"测试点修正失败: {exc}")
            raise TestPointRevisionError(
                f"test point revision failed: {exc}"
            ) from exc

    @staticmethod
    def _validate_prerequisites(state: TestAnalysisState) -> None:
        if not state.test_points:
            raise TestPointRevisionError(
                "structured test points must be generated first"
            )
        if not state.review_result or state.review_passed is None:
            raise TestPointRevisionError(
                "a completed review is required before revision"
            )
        if state.review_passed:
            raise TestPointRevisionError(
                "passing test points must not be revised automatically"
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
