import unittest

from agent.human_feedback import HumanFeedbackHandler
from agent.orchestrator import (
    AgentOrchestrator,
    OrchestrationError,
    OrchestratorAction,
)
from agent.state import (
    AgentStatus,
    KnowledgeRetrievalStatus,
    TestAnalysisState,
)


def analyzed_state() -> TestAnalysisState:
    state = TestAnalysisState("用户提交订单")
    state.requirement_summary = "订单提交"
    state.requirement_facts = ["用户可以提交订单"]
    return state


def generated_state() -> TestAnalysisState:
    state = analyzed_state()
    state.knowledge_retrieval_status = KnowledgeRetrievalStatus.NO_MATCH
    state.test_points = [{"title": "正常提交订单"}]
    return state


class RecordingNode:
    def __init__(self, callback=None):
        self.calls = 0
        self.callback = callback

    def _run(self, state):
        self.calls += 1
        if self.callback:
            self.callback(state, self.calls)

    analyze = _run
    retrieve = _run
    generate = _run
    review = _run
    revise = _run


class AgentOrchestratorDecisionTests(unittest.TestCase):
    def setUp(self):
        node = RecordingNode()
        self.orchestrator = AgentOrchestrator(
            requirement_analyzer=node,
            knowledge_retriever=node,
            test_point_generator=node,
            test_point_reviewer=node,
            test_point_reviser=node,
        )

    def test_new_task_starts_with_requirement_analysis(self):
        decision = self.orchestrator.decide_next(
            TestAnalysisState("订单需求")
        )
        self.assertEqual(
            decision.action,
            OrchestratorAction.ANALYZE_REQUIREMENT,
        )

    def test_analyzed_task_retrieves_knowledge(self):
        decision = self.orchestrator.decide_next(analyzed_state())
        self.assertEqual(
            decision.action,
            OrchestratorAction.RETRIEVE_KNOWLEDGE,
        )

    def test_generated_task_requires_review(self):
        decision = self.orchestrator.decide_next(generated_state())
        self.assertEqual(
            decision.action,
            OrchestratorAction.REVIEW_TEST_POINTS,
        )

    def test_passing_task_is_ready_for_finalization(self):
        state = generated_state()
        state.review_result = {"overall_score": 90}
        state.review_passed = True
        decision = self.orchestrator.decide_next(state)
        self.assertEqual(
            decision.action,
            OrchestratorAction.READY_FOR_FINALIZATION,
        )

    def test_failed_review_revises_below_limit(self):
        state = generated_state()
        state.review_result = {"overall_score": 70}
        state.review_passed = False
        decision = self.orchestrator.decide_next(state)
        self.assertEqual(
            decision.action,
            OrchestratorAction.REVISE_TEST_POINTS,
        )

    def test_revision_limit_stops_automatic_loop(self):
        state = generated_state()
        state.review_result = {"overall_score": 70}
        state.review_passed = False
        state.revision_count = 2
        decision = self.orchestrator.decide_next(state)
        self.assertEqual(
            decision.action,
            OrchestratorAction.REVISION_LIMIT_REACHED,
        )

    def test_waiting_and_terminal_states_stop(self):
        waiting = generated_state()
        waiting.status = AgentStatus.WAITING_FOR_USER
        failed = generated_state()
        failed.status = AgentStatus.FAILED

        self.assertEqual(
            self.orchestrator.decide_next(waiting).action,
            OrchestratorAction.WAIT_FOR_USER,
        )
        self.assertEqual(
            self.orchestrator.decide_next(failed).action,
            OrchestratorAction.TERMINAL,
        )

    def test_ready_human_feedback_overrides_passing_review(self):
        state = generated_state()
        state.review_result = {"overall_score": 90}
        state.review_passed = True
        HumanFeedbackHandler().submit(
            state,
            {
                "action": "add",
                "feedback_type": "test_suggestion",
                "target": "订单异常",
                "content": "增加重复提交场景",
                "reason": "人工评审发现遗漏",
            },
        )

        decision = self.orchestrator.decide_next(state)

        self.assertEqual(
            decision.action,
            OrchestratorAction.REVISE_TEST_POINTS,
        )


class AgentOrchestratorExecutionTests(unittest.TestCase):
    def test_run_until_blocked_executes_controlled_loop(self):
        analyzer = RecordingNode(
            lambda state, _: (
                setattr(state, "requirement_summary", "订单提交"),
                setattr(
                    state,
                    "requirement_facts",
                    ["用户可以提交订单"],
                ),
                setattr(state, "status", AgentStatus.RUNNING),
            )
        )
        retriever = RecordingNode(
            lambda state, _: setattr(
                state,
                "knowledge_retrieval_status",
                KnowledgeRetrievalStatus.NO_MATCH,
            )
        )
        generator = RecordingNode(
            lambda state, _: setattr(
                state,
                "test_points",
                [{"title": "正常提交订单"}],
            )
        )

        def review_callback(state, call_count):
            state.review_result = {
                "overall_score": 70 if call_count == 1 else 90
            }
            state.review_passed = call_count > 1

        reviewer = RecordingNode(review_callback)

        def revise_callback(state, _):
            state.revision_count += 1
            state.review_passed = None

        reviser = RecordingNode(revise_callback)
        orchestrator = AgentOrchestrator(
            requirement_analyzer=analyzer,
            knowledge_retriever=retriever,
            test_point_generator=generator,
            test_point_reviewer=reviewer,
            test_point_reviser=reviser,
            max_revision_count=2,
        )
        state = TestAnalysisState("订单需求")

        decisions = orchestrator.run_until_blocked(state)

        self.assertEqual(
            [decision.action for decision in decisions],
            [
                OrchestratorAction.ANALYZE_REQUIREMENT,
                OrchestratorAction.RETRIEVE_KNOWLEDGE,
                OrchestratorAction.GENERATE_TEST_POINTS,
                OrchestratorAction.REVIEW_TEST_POINTS,
                OrchestratorAction.REVISE_TEST_POINTS,
                OrchestratorAction.REVIEW_TEST_POINTS,
                OrchestratorAction.READY_FOR_FINALIZATION,
            ],
        )
        self.assertEqual(reviewer.calls, 2)
        self.assertEqual(reviser.calls, 1)
        self.assertEqual(state.max_revision_count, 2)

    def test_max_steps_fails_runaway_orchestration(self):
        reviewer = RecordingNode()
        node = RecordingNode()
        orchestrator = AgentOrchestrator(
            requirement_analyzer=node,
            knowledge_retriever=node,
            test_point_generator=node,
            test_point_reviewer=reviewer,
            test_point_reviser=node,
            max_steps=2,
        )
        state = generated_state()

        with self.assertRaises(OrchestrationError):
            orchestrator.run_until_blocked(state)

        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertEqual(reviewer.calls, 2)

    def test_invalid_limits_are_rejected(self):
        node = RecordingNode()
        dependencies = {
            "requirement_analyzer": node,
            "knowledge_retriever": node,
            "test_point_generator": node,
            "test_point_reviewer": node,
            "test_point_reviser": node,
        }
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            AgentOrchestrator(
                **dependencies,
                max_revision_count=-1,
            )
        with self.assertRaisesRegex(ValueError, "must be positive"):
            AgentOrchestrator(**dependencies, max_steps=0)


if __name__ == "__main__":
    unittest.main()
