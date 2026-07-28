from dataclasses import replace

from services.llm_service import LLMService
from services.prompt_service import PromptService

from .events import AgentStep
from .models import RequirementAnalysisResult
from .state import AgentStatus, TestAnalysisState
from .structured_output import generate_and_parse_json


class RequirementAnalysisError(RuntimeError):
    """Raised when the requirement analysis node cannot complete."""


class RequirementAnalyzer:
    """Analyzes a raw requirement and writes structured results to state."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_service: PromptService | None = None,
    ):
        self.llm_service = llm_service or LLMService()
        self.prompt_service = prompt_service or PromptService()

    def analyze(
        self,
        state: TestAnalysisState,
    ) -> RequirementAnalysisResult:
        state.start_step(
            AgentStep.ANALYZE_REQUIREMENT,
            "正在分析需求结构与信息边界",
        )

        try:
            system_prompt = self.prompt_service.load_system_prompt(
                "requirement_analysis"
            )
            user_prompt = (
                self.prompt_service.build_requirement_analysis_prompt(
                    state.requirement,
                    user_clarifications=state.user_clarifications,
                    deferred_questions=state.deferred_questions,
                )
            )
            result = generate_and_parse_json(
                self.llm_service,
                user_prompt,
                system_prompt,
                RequirementAnalysisResult.from_json,
            )
            if state.deferred_questions:
                result = replace(
                    result,
                    open_questions=[
                        question
                        for question in result.open_questions
                        if question not in state.deferred_questions
                    ],
                )
            self._apply_result(state, result)

            state.complete_step(
                AgentStep.ANALYZE_REQUIREMENT,
                "需求结构化分析完成",
                {
                    "module_count": len(result.modules),
                    "fact_count": len(result.requirement_facts),
                    "risk_count": len(result.inferred_risks),
                    "open_question_count": len(result.open_questions),
                },
            )

            if result.open_questions:
                state.wait_for_user(result.open_questions)

            return result
        except Exception as exc:
            state.fail(f"需求分析失败: {exc}")
            raise RequirementAnalysisError(
                f"requirement analysis failed: {exc}"
            ) from exc

    def reanalyze_with_clarifications(
        self,
        state: TestAnalysisState,
        answers: dict[str, str | None],
    ) -> RequirementAnalysisResult:
        if state.status != AgentStatus.WAITING_FOR_USER:
            raise RequirementAnalysisError(
                "task must be waiting for user clarification"
            )
        expected_questions = list(state.open_questions)
        if set(answers) != set(expected_questions):
            raise RequirementAnalysisError(
                "answers must match all current open questions"
            )

        for question in expected_questions:
            raw_answer = answers[question]
            answer = raw_answer.strip() if isinstance(raw_answer, str) else ""
            if answer:
                state.user_clarifications.append(
                    {"question": question, "answer": answer}
                )
            elif question not in state.deferred_questions:
                state.deferred_questions.append(question)

        state.open_questions = []
        state.resume()
        return self.analyze(state)

    @staticmethod
    def _apply_result(
        state: TestAnalysisState,
        result: RequirementAnalysisResult,
    ) -> None:
        state.requirement_summary = result.summary
        state.modules = list(result.modules)
        state.requirement_facts = list(result.requirement_facts)
        state.business_rules = list(result.business_rules)
        state.state_transitions = list(result.state_transitions)
        state.inferred_risks = [
            risk.to_dict() for risk in result.inferred_risks
        ]
        state.open_questions = list(result.open_questions)
