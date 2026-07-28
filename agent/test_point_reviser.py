from copy import deepcopy

from services.llm_service import LLMService
from services.prompt_service import PromptService

from .events import AgentStep
from .human_feedback import (
    FeedbackAction,
    HumanFeedback,
    HumanFeedbackHandler,
)
from .models import (
    TestPointGenerationResult,
    TestPointRevisionPlan,
)
from .state import TestAnalysisState
from .structured_output import (
    LARGE_STRUCTURED_OUTPUT_MAX_TOKENS,
    generate_and_parse_json,
)


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
            ready_feedback = HumanFeedbackHandler.ready_feedback(state)
            allowed_actions, max_operations = self._revision_scope(
                ready_feedback
            )
            system_prompt = self.prompt_service.load_system_prompt(
                "test_point_revision"
            )
            user_prompt = (
                self.prompt_service.build_test_point_revision_prompt(
                    self._requirement_analysis_payload(state),
                    original_test_points,
                    review_result=(
                        None
                        if ready_feedback
                        else state.review_result
                    ),
                    human_feedback=[
                        feedback.to_dict()
                        for feedback in ready_feedback
                    ],
                    allowed_actions=allowed_actions,
                    max_operations=max_operations,
                )
            )

            def parse_revision_plan(
                raw_response: str,
            ) -> TestPointRevisionPlan:
                plan = TestPointRevisionPlan.from_json(raw_response)
                self._validate_revision_scope(
                    plan,
                    allowed_actions,
                    max_operations,
                )
                return plan

            revision_plan = generate_and_parse_json(
                self.llm_service,
                user_prompt,
                system_prompt,
                parse_revision_plan,
                max_tokens=LARGE_STRUCTURED_OUTPUT_MAX_TOKENS,
            )
            result = revision_plan.apply_to(original_test_points)
            revised_test_points = [
                test_point.to_dict()
                for test_point in result.test_points
            ]

            state.test_points = revised_test_points
            state.revision_count += 1
            revision_source = (
                "human_feedback" if ready_feedback else "automatic_review"
            )
            if ready_feedback:
                state.human_revision_count += 1
            else:
                state.automatic_revision_count += 1
            state.revision_history.append(
                {
                    "revision_count": state.revision_count,
                    "revision_source": revision_source,
                    "before_test_points": deepcopy(
                        original_test_points
                    ),
                    "after_test_points": deepcopy(
                        revised_test_points
                    ),
                    "review_result": deepcopy(state.review_result),
                    "applied_feedback_ids": [
                        feedback.feedback_id
                        for feedback in ready_feedback
                    ],
                }
            )
            state.review_passed = None
            applied_feedback_count = (
                HumanFeedbackHandler.mark_ready_as_applied(state)
            )
            state.complete_step(
                AgentStep.REVISE_TEST_POINTS,
                "测试点定向修正完成，等待重新评审",
                {
                    "revision_count": state.revision_count,
                    "automatic_revision_count": (
                        state.automatic_revision_count
                    ),
                    "human_revision_count": state.human_revision_count,
                    "revision_source": revision_source,
                    "before_count": len(original_test_points),
                    "after_count": len(revised_test_points),
                    "previous_review_score": (
                        state.review_result or {}
                    ).get("overall_score"),
                    "review_invalidated": True,
                    "applied_feedback_count": applied_feedback_count,
                    "operation_count": len(
                        revision_plan.operations
                    ),
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
        ready_feedback = HumanFeedbackHandler.ready_feedback(state)
        has_failed_review = (
            bool(state.review_result)
            and state.review_passed is False
        )
        if (
            state.review_passed is True
            and not ready_feedback
        ):
            raise TestPointRevisionError(
                "passing test points must not be revised automatically"
            )
        if not has_failed_review and not ready_feedback:
            raise TestPointRevisionError(
                "a failed review or ready human feedback is required"
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

    @staticmethod
    def _revision_scope(
        ready_feedback: list[HumanFeedback],
    ) -> tuple[set[str], int]:
        if not ready_feedback:
            return {"add", "replace", "remove"}, 20

        action_mapping = {
            FeedbackAction.ADD: {"add", "replace"},
            FeedbackAction.REMOVE: {"remove"},
            FeedbackAction.MODIFY: {"replace"},
            FeedbackAction.UPDATE_PRIORITY: {"replace"},
        }
        allowed_actions: set[str] = set()
        max_operations = 0
        for feedback in ready_feedback:
            allowed_actions.update(action_mapping[feedback.action])
            max_operations += (
                3 if feedback.action == FeedbackAction.ADD else 1
            )
        return allowed_actions, min(max_operations, 6)

    @staticmethod
    def _validate_revision_scope(
        plan: TestPointRevisionPlan,
        allowed_actions: set[str],
        max_operations: int,
    ) -> None:
        if len(plan.operations) > max_operations:
            raise ValueError(
                "revision operation count exceeds the allowed scope: "
                f"{len(plan.operations)} > {max_operations}"
            )
        unexpected_actions = {
            operation.action
            for operation in plan.operations
            if operation.action not in allowed_actions
        }
        if unexpected_actions:
            raise ValueError(
                "revision contains actions outside the feedback scope: "
                + ", ".join(sorted(unexpected_actions))
            )
