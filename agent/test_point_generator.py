from services.llm_service import LLMService
from services.prompt_service import PromptService

from .events import AgentStep
from .context_builder import ContextBuilder
from .models import TestPointGenerationResult
from .state import KnowledgeRetrievalStatus, TestAnalysisState
from .structured_output import (
    LARGE_STRUCTURED_OUTPUT_MAX_TOKENS,
    generate_and_parse_json,
)


class TestPointGenerationError(RuntimeError):
    """Raised when the test point generation node cannot complete."""


class TestPointGenerator:
    """Generates validated structured test points and writes them to state."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_service: PromptService | None = None,
        context_builder: ContextBuilder | None = None,
    ):
        self.llm_service = llm_service or LLMService()
        self.prompt_service = prompt_service or PromptService()
        self.context_builder = context_builder or ContextBuilder()

    def generate(
        self,
        state: TestAnalysisState,
    ) -> TestPointGenerationResult:
        self._validate_prerequisites(state)
        state.start_step(
            AgentStep.GENERATE_TEST_POINTS,
            "正在生成结构化测试点",
        )

        try:
            system_prompt = self.prompt_service.load_system_prompt(
                "structured_test_points"
            )
            context = self.context_builder.build_test_point_generation(state)
            user_prompt = (
                self.prompt_service.build_structured_test_points_prompt(
                    context.values["requirement_analysis"],
                    local_bug_knowledge=context.values[
                        "local_bug_knowledge"
                    ],
                    rag_context=context.values["rag_context"],
                )
            )
            result = generate_and_parse_json(
                self.llm_service,
                user_prompt,
                system_prompt,
                TestPointGenerationResult.from_json,
                max_tokens=LARGE_STRUCTURED_OUTPUT_MAX_TOKENS,
            )
            state.test_points = [
                test_point.to_dict()
                for test_point in result.test_points
            ]
            state.complete_step(
                AgentStep.GENERATE_TEST_POINTS,
                "结构化测试点生成完成",
                {
                    "test_point_count": len(result.test_points),
                    "category_counts": self._category_counts(result),
                    "priority_counts": self._priority_counts(result),
                    "context_metrics": context.metrics.to_dict(),
                },
            )
            return result
        except Exception as exc:
            state.fail(f"测试点生成失败: {exc}")
            raise TestPointGenerationError(
                f"test point generation failed: {exc}"
            ) from exc

    @staticmethod
    def _validate_prerequisites(state: TestAnalysisState) -> None:
        if not state.requirement_summary or not state.requirement_facts:
            raise TestPointGenerationError(
                "requirement analysis must be completed first"
            )
        if state.open_questions:
            raise TestPointGenerationError(
                "open questions must be resolved before generation"
            )
        if (
            state.knowledge_retrieval_status
            == KnowledgeRetrievalStatus.NOT_STARTED
        ):
            raise TestPointGenerationError(
                "knowledge retrieval must be attempted first"
            )

    @staticmethod
    def _category_counts(
        result: TestPointGenerationResult,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for test_point in result.test_points:
            key = test_point.category.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    @staticmethod
    def _priority_counts(
        result: TestPointGenerationResult,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for test_point in result.test_points:
            key = test_point.priority.value
            counts[key] = counts.get(key, 0) + 1
        return counts
