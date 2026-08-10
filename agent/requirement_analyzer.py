from dataclasses import replace
import re

from services.llm_service import LLMService
from services.prompt_service import PromptService

from .events import AgentStep
from .clarification_policy import ClarificationQuestionPolicy
from .context_builder import ContextBuilder
from .models import RequirementAnalysisResult
from .models import ClarificationCandidate, InferredRisk
from .requirement_chunking import RequirementChunk, RequirementChunker
from .state import AgentStatus, TestAnalysisState
from .structured_output import (
    LARGE_STRUCTURED_OUTPUT_MAX_TOKENS,
    generate_and_parse_json,
)


class RequirementAnalysisError(RuntimeError):
    """Raised when the requirement analysis node cannot complete."""


class RequirementAnalyzer:
    """Analyzes a raw requirement and writes structured results to state."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_service: PromptService | None = None,
        clarification_policy: ClarificationQuestionPolicy | None = None,
        context_builder: ContextBuilder | None = None,
        chunker: RequirementChunker | None = None,
    ):
        self.llm_service = llm_service or LLMService()
        self.prompt_service = prompt_service or PromptService()
        self.clarification_policy = (
            clarification_policy or ClarificationQuestionPolicy()
        )
        self.context_builder = context_builder or ContextBuilder()
        self.chunker = chunker or RequirementChunker()

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
            context = self.context_builder.build_requirement_analysis(state)
            chunks = self.chunker.split(context.values["requirement"])
            partial_results = [
                self._analyze_chunk(
                    chunk,
                    system_prompt=system_prompt,
                    user_clarifications=context.values["user_clarifications"],
                    deferred_questions=context.values["deferred_questions"],
                )
                for chunk in chunks
            ]
            result = self._merge_results(partial_results)
            raw_candidate_count = sum(
                len(item.clarification_candidates)
                for item in partial_results
            )
            selection = self.clarification_policy.select(
                result.clarification_candidates,
                deferred_questions=state.deferred_questions,
            )
            result = replace(
                result,
                clarification_candidates=list(selection.blocking),
                inferred_risks=[
                    *result.inferred_risks,
                    *selection.non_blocking_risks,
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
                    "clarification_candidate_count": raw_candidate_count,
                    "non_blocking_question_count": len(
                        selection.non_blocking_risks
                    ),
                    "requirement_chunk_count": len(chunks),
                    "requirement_chunked": len(chunks) > 1,
                    "context_metrics": context.metrics.to_dict(),
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

    def _analyze_chunk(
        self,
        chunk: RequirementChunk,
        *,
        system_prompt: str,
        user_clarifications: list[dict],
        deferred_questions: list[str],
    ) -> RequirementAnalysisResult:
        source_label = f"{chunk.chunk_id}｜{chunk.title}"
        user_prompt = self.prompt_service.build_requirement_analysis_prompt(
            chunk.content,
            user_clarifications=user_clarifications,
            deferred_questions=deferred_questions,
            source_label=source_label,
        )
        try:
            result = generate_and_parse_json(
                self.llm_service,
                user_prompt,
                system_prompt,
                RequirementAnalysisResult.from_json,
                max_tokens=LARGE_STRUCTURED_OUTPUT_MAX_TOKENS,
            )
        except Exception as exc:
            raise RequirementAnalysisError(
                f"{source_label} 分析失败: {exc}"
            ) from exc
        return replace(
            result,
            inferred_risks=[
                InferredRisk(
                    risk=item.risk,
                    basis=f"[{source_label}] {item.basis}",
                )
                for item in result.inferred_risks
            ],
            clarification_candidates=[
                ClarificationCandidate(
                    question=item.question,
                    category=item.category,
                    blocking_reason=item.blocking_reason,
                    evidence=f"[{source_label}] {item.evidence}",
                )
                for item in result.clarification_candidates
            ],
        )

    @classmethod
    def _merge_results(
        cls,
        results: list[RequirementAnalysisResult],
    ) -> RequirementAnalysisResult:
        if not results:
            raise RequirementAnalysisError("requirement analysis produced no result")
        return RequirementAnalysisResult(
            summary="；".join(cls._unique(item.summary for item in results)),
            modules=cls._unique(
                value for item in results for value in item.modules
            ),
            requirement_facts=cls._unique(
                value for item in results for value in item.requirement_facts
            ),
            business_rules=cls._unique(
                value for item in results for value in item.business_rules
            ),
            state_transitions=cls._unique(
                value for item in results for value in item.state_transitions
            ),
            inferred_risks=cls._unique_by(
                (value for item in results for value in item.inferred_risks),
                lambda value: value.risk,
            ),
            clarification_candidates=cls._unique_by(
                (
                    value
                    for item in results
                    for value in item.clarification_candidates
                ),
                lambda value: value.question,
            ),
        )

    @classmethod
    def _unique(cls, values) -> list[str]:
        return cls._unique_by(values, lambda value: value)

    @classmethod
    def _unique_by(cls, values, key) -> list:
        seen: set[str] = set()
        unique = []
        for value in values:
            normalized = re.sub(
                r"[\s，,。；;：:！？!?]",
                "",
                key(value),
            ).casefold()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(value)
        return unique

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
