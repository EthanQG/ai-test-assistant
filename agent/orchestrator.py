from dataclasses import dataclass
from enum import Enum

from .finalizer import Finalizer
from .human_feedback import HumanFeedbackHandler
from .knowledge_retriever import KnowledgeRetriever
from .requirement_analyzer import RequirementAnalyzer
from .state import (
    AgentStatus,
    KnowledgeRetrievalStatus,
    TestAnalysisState,
)
from .test_point_generator import TestPointGenerator
from .test_point_reviewer import TestPointReviewer
from .test_point_reviser import TestPointReviser


class OrchestratorAction(str, Enum):
    ANALYZE_REQUIREMENT = "analyze_requirement"
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
    GENERATE_TEST_POINTS = "generate_test_points"
    REVIEW_TEST_POINTS = "review_test_points"
    REVISE_TEST_POINTS = "revise_test_points"
    FINALIZE = "finalize"
    WAIT_FOR_USER = "wait_for_user"
    REVISION_LIMIT_REACHED = "revision_limit_reached"
    TERMINAL = "terminal"


STOP_ACTIONS = {
    OrchestratorAction.WAIT_FOR_USER,
    OrchestratorAction.REVISION_LIMIT_REACHED,
    OrchestratorAction.TERMINAL,
}


@dataclass(frozen=True)
class OrchestratorDecision:
    action: OrchestratorAction
    reason: str


class OrchestrationError(RuntimeError):
    """Raised when controlled orchestration cannot progress safely."""


class AgentOrchestrator:
    """Selects and executes the only legal next node using Python rules."""

    def __init__(
        self,
        requirement_analyzer: RequirementAnalyzer | None = None,
        knowledge_retriever: KnowledgeRetriever | None = None,
        test_point_generator: TestPointGenerator | None = None,
        test_point_reviewer: TestPointReviewer | None = None,
        test_point_reviser: TestPointReviser | None = None,
        finalizer: Finalizer | None = None,
        max_revision_count: int = 2,
        max_steps: int = 20,
    ):
        if max_revision_count < 0:
            raise ValueError("max_revision_count cannot be negative")
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        self.requirement_analyzer = (
            requirement_analyzer or RequirementAnalyzer()
        )
        self.knowledge_retriever = (
            knowledge_retriever or KnowledgeRetriever()
        )
        self.test_point_generator = (
            test_point_generator or TestPointGenerator()
        )
        self.test_point_reviewer = (
            test_point_reviewer or TestPointReviewer()
        )
        self.test_point_reviser = (
            test_point_reviser or TestPointReviser()
        )
        self.finalizer = finalizer or Finalizer()
        self.max_revision_count = max_revision_count
        self.max_steps = max_steps

    def decide_next(
        self,
        state: TestAnalysisState,
    ) -> OrchestratorDecision:
        if state.status in {AgentStatus.COMPLETED, AgentStatus.FAILED}:
            return OrchestratorDecision(
                OrchestratorAction.TERMINAL,
                f"任务已处于终态: {state.status.value}",
            )
        if state.status == AgentStatus.WAITING_FOR_USER:
            return OrchestratorDecision(
                OrchestratorAction.WAIT_FOR_USER,
                "任务正在等待用户确认或补充信息",
            )
        if not state.requirement_summary:
            return OrchestratorDecision(
                OrchestratorAction.ANALYZE_REQUIREMENT,
                "尚未完成结构化需求分析",
            )
        if state.open_questions:
            return OrchestratorDecision(
                OrchestratorAction.WAIT_FOR_USER,
                "仍有待确认需求问题",
            )
        if (
            state.knowledge_retrieval_status
            == KnowledgeRetrievalStatus.NOT_STARTED
        ):
            return OrchestratorDecision(
                OrchestratorAction.RETRIEVE_KNOWLEDGE,
                "尚未尝试历史知识检索",
            )
        if not state.test_points:
            return OrchestratorDecision(
                OrchestratorAction.GENERATE_TEST_POINTS,
                "尚未生成结构化测试点",
            )

        ready_feedback = HumanFeedbackHandler.ready_feedback(state)
        if ready_feedback:
            if state.revision_count >= self.max_revision_count:
                return OrchestratorDecision(
                    OrchestratorAction.REVISION_LIMIT_REACHED,
                    "已达到自动修正次数上限，人工反馈尚未应用",
                )
            return OrchestratorDecision(
                OrchestratorAction.REVISE_TEST_POINTS,
                "存在已确认、尚未应用的人工反馈",
            )

        if state.review_passed is None:
            return OrchestratorDecision(
                OrchestratorAction.REVIEW_TEST_POINTS,
                "当前测试点尚未完成有效评审",
            )
        if state.review_passed:
            return OrchestratorDecision(
                OrchestratorAction.FINALIZE,
                "当前测试点已通过质量评审",
            )
        if state.revision_count >= self.max_revision_count:
            return OrchestratorDecision(
                OrchestratorAction.REVISION_LIMIT_REACHED,
                "评审未通过且已达到自动修正次数上限",
            )
        return OrchestratorDecision(
            OrchestratorAction.REVISE_TEST_POINTS,
            "评审未通过且仍可进行定向修正",
        )

    def run_next(
        self,
        state: TestAnalysisState,
    ) -> OrchestratorDecision:
        state.max_revision_count = self.max_revision_count
        decision = self.decide_next(state)
        action = decision.action

        if action == OrchestratorAction.ANALYZE_REQUIREMENT:
            self.requirement_analyzer.analyze(state)
        elif action == OrchestratorAction.RETRIEVE_KNOWLEDGE:
            self.knowledge_retriever.retrieve(state)
        elif action == OrchestratorAction.GENERATE_TEST_POINTS:
            self.test_point_generator.generate(state)
        elif action == OrchestratorAction.REVIEW_TEST_POINTS:
            self.test_point_reviewer.review(state)
        elif action == OrchestratorAction.REVISE_TEST_POINTS:
            self.test_point_reviser.revise(state)
        elif action == OrchestratorAction.FINALIZE:
            self.finalizer.finalize(state)
        return decision

    def run_until_blocked(
        self,
        state: TestAnalysisState,
    ) -> list[OrchestratorDecision]:
        decisions = []
        for _ in range(self.max_steps):
            decision = self.run_next(state)
            decisions.append(decision)
            if decision.action in STOP_ACTIONS:
                return decisions

        if state.status in {AgentStatus.COMPLETED, AgentStatus.FAILED}:
            return decisions

        message = (
            f"orchestration exceeded maximum step count: {self.max_steps}"
        )
        state.fail(message)
        raise OrchestrationError(message)
