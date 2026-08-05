import unittest
from copy import deepcopy

from agent import (
    AgentEvent,
    AgentOrchestrator,
    AgentStatus,
    AgentStep,
    HumanFeedbackHandler,
    HumanFeedbackValidationError,
    KnowledgeRetrievalStatus,
    OrchestratorAction,
    TestAnalysisState,
)
from application import (
    ConfirmBusinessRulesCommand,
    SubmitClarificationsCommand,
    TaskRecord,
    TaskSnapshotSerializer,
    TestAnalysisApplicationService,
)
from repositories import InMemoryTaskRepository

from .test_task_snapshots import (
    REVIEW_RESULT,
    TEST_POINT,
    build_full_record,
)


def _passing_review_result() -> dict:
    result = deepcopy(REVIEW_RESULT)
    result["overall_score"] = 90
    result["missing_scenarios"] = []
    result["revision_suggestions"] = []
    return result


def _generated_state() -> TestAnalysisState:
    state = TestAnalysisState("用户提交订单时校验库存")
    state.requirement_summary = "订单创建与库存扣减"
    state.requirement_facts = ["库存充足时创建订单"]
    state.knowledge_retrieval_status = KnowledgeRetrievalStatus.NO_MATCH
    state.test_points = [deepcopy(TEST_POINT)]
    return state


def _round_trip(record: TaskRecord) -> TaskRecord:
    payload = TaskSnapshotSerializer.to_dict(record)
    raw_snapshot = TaskSnapshotSerializer.to_json(record)
    restored = TaskSnapshotSerializer.from_json(raw_snapshot)
    assert TaskSnapshotSerializer.to_dict(restored) == payload
    return restored


def _build_service(
    record: TaskRecord,
    orchestrator: AgentOrchestrator,
) -> tuple[TestAnalysisApplicationService, InMemoryTaskRepository]:
    repository = InMemoryTaskRepository()
    repository.create(record)
    service = TestAnalysisApplicationService(
        repository,
        orchestrator_factory=lambda: orchestrator,
        knowledge_loader=lambda: "脱敏缺陷经验",
    )
    return service, repository


class FakeRequirementAnalyzer:
    def __init__(self):
        self.analyze_calls = 0
        self.clarification_calls = 0

    def analyze(self, state):
        self.analyze_calls += 1

    def reanalyze_with_clarifications(self, state, answers):
        self.clarification_calls += 1
        expected_questions = list(state.open_questions)
        state.resume()
        state.user_clarifications.extend(
            {
                "question": question,
                "answer": answers[question],
            }
            for question in expected_questions
        )
        state.open_questions = []
        state.requirement_summary = "补充后的订单需求"
        state.requirement_facts = ["库存充足时创建订单"]


class FakeNode:
    def __init__(self):
        self.calls = 0

    def retrieve(self, state):
        del state
        self.calls += 1

    def generate(self, state):
        del state
        self.calls += 1


class FakeReviser:
    def __init__(self):
        self.calls = 0

    def revise(self, state):
        self.calls += 1
        before = deepcopy(state.test_points)
        ready_feedback = HumanFeedbackHandler.ready_feedback(state)
        state.start_step(
            AgentStep.REVISE_TEST_POINTS,
            "Fake Reviser开始修正",
        )
        state.revision_count += 1
        if ready_feedback:
            state.human_revision_count += 1
            revision_source = "human_feedback"
        else:
            state.automatic_revision_count += 1
            revision_source = "automatic_review"
        state.revision_history.append(
            {
                "revision_count": state.revision_count,
                "revision_source": revision_source,
                "before_test_points": before,
                "after_test_points": deepcopy(state.test_points),
                "review_result": deepcopy(state.review_result),
                "applied_feedback_ids": [
                    feedback.feedback_id
                    for feedback in ready_feedback
                ],
            }
        )
        HumanFeedbackHandler.mark_ready_as_applied(state)
        state.review_passed = None
        state.complete_step(
            AgentStep.REVISE_TEST_POINTS,
            "Fake Reviser修正完成",
        )


class FakeReviewer:
    def __init__(self):
        self.calls = 0

    def review(self, state):
        self.calls += 1
        state.start_step(
            AgentStep.REVIEW_TEST_POINTS,
            "Fake Reviewer开始评审",
        )
        result = _passing_review_result()
        state.review_result = result
        state.review_passed = True
        state.review_history.append(
            {
                "review_round": len(state.review_history) + 1,
                "revision_count": state.revision_count,
                "automatic_revision_count": (
                    state.automatic_revision_count
                ),
                "human_revision_count": state.human_revision_count,
                "passed": True,
                "result": deepcopy(result),
            }
        )
        state.complete_step(
            AgentStep.REVIEW_TEST_POINTS,
            "Fake Reviewer评审完成",
        )


class FakeFinalizer:
    def __init__(self):
        self.calls = 0

    def finalize(self, state):
        self.calls += 1
        state.final_result = {
            "test_point_count": len(state.test_points),
        }
        state.complete("# Fake最终报告")


class CountingAgentOrchestrator(AgentOrchestrator):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.decide_calls = 0
        self.run_calls = 0
        self.resume_calls = 0

    def decide_next(self, state):
        self.decide_calls += 1
        return super().decide_next(state)

    def run_next(self, state):
        self.run_calls += 1
        return super().run_next(state)

    def resume_with_clarifications(self, state, answers):
        self.resume_calls += 1
        return super().resume_with_clarifications(state, answers)


class TaskSnapshotRecoveryExecutionTests(unittest.TestCase):
    def test_snapshot_restored_task_continues_execution_after_clarifications(
        self,
    ):
        state = TestAnalysisState("用户提交订单时校验库存")
        state.wait_for_user(["是否允许库存超卖？"])
        restored = _round_trip(
            TaskRecord(
                state=state,
                auto_run=False,
                next_action=OrchestratorAction.WAIT_FOR_USER.value,
            )
        )
        analyzer = FakeRequirementAnalyzer()
        orchestrator = CountingAgentOrchestrator(
            requirement_analyzer=analyzer,
            knowledge_retriever=FakeNode(),
            test_point_generator=FakeNode(),
            test_point_reviewer=FakeReviewer(),
            test_point_reviser=FakeReviser(),
            finalizer=FakeFinalizer(),
        )
        service, _ = _build_service(restored, orchestrator)

        pending = service.submit_clarifications(
            state.task_id,
            SubmitClarificationsCommand(
                {"是否允许库存超卖？": "不允许"}
            ),
        )
        resumed = service.advance_task(state.task_id)

        self.assertIsInstance(
            restored.state.events[0],
            AgentEvent,
        )
        self.assertEqual(pending.task_id, state.task_id)
        self.assertTrue(pending.has_pending_clarifications)
        self.assertEqual(orchestrator.resume_calls, 1)
        self.assertEqual(analyzer.clarification_calls, 1)
        self.assertEqual(resumed.task_id, state.task_id)
        self.assertEqual(resumed.status, AgentStatus.RUNNING)
        self.assertEqual(
            resumed.next_action,
            OrchestratorAction.RETRIEVE_KNOWLEDGE.value,
        )
        self.assertEqual(
            resumed.decisions[-1].action,
            OrchestratorAction.ANALYZE_REQUIREMENT,
        )
        self.assertEqual(
            resumed.user_clarifications[0]["answer"],
            "不允许",
        )

    def test_snapshot_restored_task_continues_execution_after_business_rule_confirmation(
        self,
    ):
        state, feedback_id = self._pending_business_rule_state()
        restored = _round_trip(
            TaskRecord(
                state=state,
                auto_run=False,
                next_action=OrchestratorAction.WAIT_FOR_USER.value,
            )
        )
        reviser = FakeReviser()
        orchestrator = self._orchestrator(test_point_reviser=reviser)
        service, _ = _build_service(restored, orchestrator)

        with self.assertRaises(HumanFeedbackValidationError):
            service.confirm_business_rules(
                state.task_id,
                ConfirmBusinessRulesCommand(
                    feedback_id="unknown-feedback",
                    confirmed=True,
                ),
            )
        confirmed = service.confirm_business_rules(
            state.task_id,
            ConfirmBusinessRulesCommand(
                feedback_id=feedback_id,
                confirmed=True,
            ),
        )
        revised = service.advance_task(state.task_id)

        self.assertIn("库存不得为负数", confirmed.business_rules)
        self.assertEqual(
            confirmed.human_feedback[0]["status"],
            "ready",
        )
        self.assertEqual(
            confirmed.next_action,
            OrchestratorAction.REVISE_TEST_POINTS.value,
        )
        self.assertEqual(reviser.calls, 1)
        self.assertEqual(revised.revision_count, 1)
        self.assertEqual(revised.human_revision_count, 1)
        self.assertEqual(
            revised.human_feedback[0]["status"],
            "applied",
        )
        self.assertEqual(
            revised.next_action,
            OrchestratorAction.REVIEW_TEST_POINTS.value,
        )

    def test_snapshot_restored_task_continues_execution_after_business_rule_rejection(
        self,
    ):
        state, feedback_id = self._pending_business_rule_state()
        restored = _round_trip(
            TaskRecord(
                state=state,
                auto_run=False,
                next_action=OrchestratorAction.WAIT_FOR_USER.value,
            )
        )
        finalizer = FakeFinalizer()
        orchestrator = self._orchestrator(finalizer=finalizer)
        service, _ = _build_service(restored, orchestrator)

        rejected = service.confirm_business_rules(
            state.task_id,
            ConfirmBusinessRulesCommand(
                feedback_id=feedback_id,
                confirmed=False,
            ),
        )
        completed = service.advance_task(state.task_id)

        self.assertNotIn("库存不得为负数", rejected.business_rules)
        self.assertEqual(
            rejected.human_feedback[0]["status"],
            "rejected",
        )
        self.assertEqual(
            rejected.next_action,
            OrchestratorAction.FINALIZE.value,
        )
        self.assertEqual(finalizer.calls, 1)
        self.assertEqual(completed.status, AgentStatus.COMPLETED)
        self.assertEqual(completed.report, "# Fake最终报告")

    def test_snapshot_restored_task_continues_execution_through_revision_and_review(
        self,
    ):
        state = _generated_state()
        original_points = deepcopy(state.test_points)
        state.review_result = deepcopy(REVIEW_RESULT)
        state.review_passed = False
        state.review_history = [
            {
                "review_round": 1,
                "revision_count": 0,
                "automatic_revision_count": 0,
                "human_revision_count": 0,
                "passed": False,
                "result": deepcopy(REVIEW_RESULT),
            }
        ]
        restored = _round_trip(
            TaskRecord(
                state=state,
                auto_run=True,
                next_action=OrchestratorAction.REVISE_TEST_POINTS.value,
            )
        )
        reviser = FakeReviser()
        reviewer = FakeReviewer()
        orchestrator = self._orchestrator(
            test_point_reviser=reviser,
            test_point_reviewer=reviewer,
        )
        service, _ = _build_service(restored, orchestrator)

        revised = service.advance_task(state.task_id)
        reviewed = service.advance_task(state.task_id)

        self.assertEqual(reviser.calls, 1)
        self.assertEqual(revised.revision_count, 1)
        self.assertEqual(revised.automatic_revision_count, 1)
        self.assertEqual(revised.test_points, original_points)
        self.assertEqual(len(revised.revision_history), 1)
        self.assertEqual(
            revised.revision_history[0]["before_test_points"],
            original_points,
        )
        self.assertEqual(
            revised.next_action,
            OrchestratorAction.REVIEW_TEST_POINTS.value,
        )
        self.assertEqual(reviewer.calls, 1)
        self.assertTrue(reviewed.review_passed)
        self.assertEqual(len(reviewed.review_history), 2)
        self.assertEqual(reviewed.test_points, original_points)
        self.assertEqual(
            reviewed.next_action,
            OrchestratorAction.FINALIZE.value,
        )

    def test_snapshot_restored_terminal_tasks_do_not_continue_execution(
        self,
    ):
        completed_record = build_full_record()
        completed_record.state.status = AgentStatus.COMPLETED
        completed_record.state.current_step = AgentStep.FINALIZE
        completed_record.state.open_questions = []
        completed_record.auto_run = False
        completed_record.pending_clarifications = None
        completed_record.next_action = OrchestratorAction.TERMINAL.value

        failed_state = TestAnalysisState("执行失败的脱敏需求")
        failed_state.fail("模型响应超时")
        failed_record = TaskRecord(
            state=failed_state,
            auto_run=False,
            next_action=OrchestratorAction.TERMINAL.value,
        )

        for name, record in (
            ("completed", completed_record),
            ("failed", failed_record),
        ):
            with self.subTest(status=name):
                restored = _round_trip(record)
                analyzer = FakeRequirementAnalyzer()
                retriever = FakeNode()
                generator = FakeNode()
                reviewer = FakeReviewer()
                reviser = FakeReviser()
                finalizer = FakeFinalizer()
                orchestrator = CountingAgentOrchestrator(
                    requirement_analyzer=analyzer,
                    knowledge_retriever=retriever,
                    test_point_generator=generator,
                    test_point_reviewer=reviewer,
                    test_point_reviser=reviser,
                    finalizer=finalizer,
                )
                service, _ = _build_service(restored, orchestrator)

                result = service.advance_task(record.state.task_id)

                self.assertEqual(orchestrator.decide_calls, 0)
                self.assertEqual(orchestrator.run_calls, 0)
                self.assertEqual(orchestrator.resume_calls, 0)
                self.assertEqual(analyzer.analyze_calls, 0)
                self.assertEqual(analyzer.clarification_calls, 0)
                self.assertEqual(retriever.calls, 0)
                self.assertEqual(generator.calls, 0)
                self.assertEqual(reviewer.calls, 0)
                self.assertEqual(reviser.calls, 0)
                self.assertEqual(finalizer.calls, 0)
                self.assertEqual(result.status, record.state.status)
                self.assertEqual(
                    result.final_result,
                    record.state.final_result,
                )
                self.assertEqual(
                    result.error_message,
                    record.state.error_message,
                )

    @staticmethod
    def _pending_business_rule_state() -> tuple[TestAnalysisState, str]:
        state = _generated_state()
        state.review_result = _passing_review_result()
        state.review_passed = True
        feedback = HumanFeedbackHandler().submit(
            state,
            {
                "action": "add",
                "feedback_type": "business_rule",
                "target": "业务规则",
                "content": "库存不得为负数",
                "reason": "防止库存超卖",
            },
        )
        return state, feedback.feedback_id

    @staticmethod
    def _orchestrator(**overrides) -> CountingAgentOrchestrator:
        dependencies = {
            "requirement_analyzer": FakeRequirementAnalyzer(),
            "knowledge_retriever": FakeNode(),
            "test_point_generator": FakeNode(),
            "test_point_reviewer": FakeReviewer(),
            "test_point_reviser": FakeReviser(),
            "finalizer": FakeFinalizer(),
        }
        dependencies.update(overrides)
        return CountingAgentOrchestrator(**dependencies)


if __name__ == "__main__":
    unittest.main()
