import unittest

from agent import (
    AgentStatus,
    AgentStep,
    FeedbackStatus,
    HumanFeedbackHandler,
    KnowledgeRetrievalStatus,
    OrchestratorAction,
    OrchestratorDecision,
    TestAnalysisState,
)
from application import (
    ConfirmBusinessRulesCommand,
    CreateTaskCommand,
    SubmitClarificationsCommand,
    SubmitFeedbackCommand,
    TaskRecord,
    TestAnalysisApplicationService,
)
from repositories import InMemoryTaskRepository, TaskNotFoundError


class ScriptedOrchestrator:
    def __init__(self, steps):
        self.steps = list(steps)

    def decide_next(self, state):
        del state
        action = (
            self.steps[0][0]
            if self.steps
            else OrchestratorAction.TERMINAL
        )
        return OrchestratorDecision(action, "脚本化决策")

    def run_next(self, state):
        action, callback = self.steps.pop(0)
        callback(state)
        return OrchestratorDecision(
            action,
            "脚本化决策",
            duration_seconds=0.01,
        )


class FakeClarificationAnalyzer:
    def reanalyze_with_clarifications(self, state, answers):
        state.resume()
        state.user_clarifications.extend(
            {"question": question, "answer": answer or ""}
            for question, answer in answers.items()
            if answer is not None
        )
        state.deferred_questions.extend(
            question
            for question, answer in answers.items()
            if answer is None
        )
        state.open_questions = []
        state.requirement_summary = "补充后的需求"


def _create_service(orchestrator=None):
    repository = InMemoryTaskRepository()
    orchestrator = orchestrator or ScriptedOrchestrator([])
    service = TestAnalysisApplicationService(
        repository,
        orchestrator_factory=lambda: orchestrator,
        requirement_analyzer_factory=FakeClarificationAnalyzer,
        knowledge_loader=lambda: "本地缺陷经验",
    )
    return service, repository


def _seed_completed_task(repository):
    state = TestAnalysisState("用户可以使用优惠券")
    state.test_points = [{"title": "正常使用优惠券"}]
    state.review_result = {"overall_score": 90}
    state.review_passed = True
    state.status = AgentStatus.COMPLETED
    repository.create(TaskRecord(state=state))
    return state


class TestAnalysisApplicationServiceTests(unittest.TestCase):
    def test_create_task_returns_read_only_view(self):
        service, repository = _create_service()

        task = service.create_task(
            CreateTaskCommand(requirement=" 用户可以提交订单 ")
        )
        points = task.test_points
        points.append({"title": "页面侧修改"})

        self.assertEqual(task.requirement, "用户可以提交订单")
        self.assertEqual(task.local_bug_knowledge, "本地缺陷经验")
        self.assertTrue(task.auto_run)
        self.assertEqual(service.get_task(task.task_id).test_points, [])
        self.assertEqual(
            repository.get(task.task_id).state.test_points,
            [],
        )

    def test_advance_task_uses_orchestrator_decision(self):
        def wait_for_user(state):
            state.start_step(AgentStep.ANALYZE_REQUIREMENT, "分析需求")
            state.requirement_summary = "优惠券需求"
            state.complete_step(
                AgentStep.ANALYZE_REQUIREMENT,
                "需求分析完成",
            )
            state.wait_for_user(["优惠券是否允许叠加？"])

        orchestrator = ScriptedOrchestrator(
            [(OrchestratorAction.ANALYZE_REQUIREMENT, wait_for_user)]
        )
        service, _ = _create_service(orchestrator)
        task = service.create_task(
            CreateTaskCommand(requirement="用户可以使用优惠券")
        )

        result = service.advance_task(task.task_id)

        self.assertEqual(result.status, AgentStatus.WAITING_FOR_USER)
        self.assertFalse(result.auto_run)
        self.assertEqual(
            result.decisions[-1].action,
            OrchestratorAction.ANALYZE_REQUIREMENT,
        )
        self.assertEqual(len(result.metrics), 1)
        self.assertTrue(result.metrics[0].succeeded)

    def test_clarifications_resume_same_task(self):
        service, repository = _create_service()
        state = TestAnalysisState("用户可以使用优惠券")
        state.wait_for_user(["优惠券是否允许叠加？"])
        repository.create(TaskRecord(state=state))

        pending = service.submit_clarifications(
            state.task_id,
            SubmitClarificationsCommand(
                {"优惠券是否允许叠加？": "最多叠加两张"}
            ),
        )
        resumed = service.advance_task(state.task_id)

        self.assertTrue(pending.has_pending_clarifications)
        self.assertEqual(resumed.task_id, state.task_id)
        self.assertEqual(resumed.status, AgentStatus.RUNNING)
        self.assertEqual(resumed.open_questions, [])
        self.assertEqual(
            resumed.user_clarifications[0]["answer"],
            "最多叠加两张",
        )

    def test_business_rule_confirmation_cannot_be_bypassed(self):
        service, repository = _create_service()
        state = _seed_completed_task(repository)
        waiting = service.submit_feedback(
            state.task_id,
            SubmitFeedbackCommand(
                action="add",
                feedback_type="business_rule",
                target="新增业务规则",
                content="优惠券最多叠加两张",
                reason="产品补充",
            ),
        )

        unchanged = service.advance_task(state.task_id)
        feedback_id = waiting.human_feedback[0]["feedback_id"]
        confirmed = service.confirm_business_rules(
            state.task_id,
            ConfirmBusinessRulesCommand(
                feedback_id=feedback_id,
                confirmed=True,
            ),
        )

        self.assertEqual(waiting.status, AgentStatus.WAITING_FOR_USER)
        self.assertEqual(unchanged.business_rules, [])
        self.assertIn("优惠券最多叠加两张", confirmed.business_rules)
        self.assertTrue(confirmed.auto_run)

    def test_reviewer_passed_flow_reaches_completion(self):
        def review(state):
            state.review_result = {"overall_score": 90}
            state.review_passed = True

        def finalize(state):
            state.complete("# 测试分析报告")

        orchestrator = ScriptedOrchestrator(
            [
                (OrchestratorAction.REVIEW_TEST_POINTS, review),
                (OrchestratorAction.FINALIZE, finalize),
            ]
        )
        service, repository = _create_service(orchestrator)
        state = TestAnalysisState("订单需求")
        state.requirement_summary = "订单"
        state.knowledge_retrieval_status = (
            KnowledgeRetrievalStatus.NO_MATCH
        )
        state.test_points = [{"title": "提交订单"}]
        repository.create(TaskRecord(state=state, auto_run=True))

        reviewed = service.advance_task(state.task_id)
        completed = service.advance_task(state.task_id)

        self.assertTrue(reviewed.review_passed)
        self.assertEqual(completed.status, AgentStatus.COMPLETED)
        self.assertEqual(
            [decision.action for decision in completed.decisions],
            [
                OrchestratorAction.REVIEW_TEST_POINTS,
                OrchestratorAction.FINALIZE,
            ],
        )

    def test_failed_review_uses_existing_revision_flow(self):
        def failed_review(state):
            state.review_result = {"overall_score": 60}
            state.review_passed = False

        def revise(state):
            state.automatic_revision_count += 1
            state.review_result = None
            state.review_passed = None

        orchestrator = ScriptedOrchestrator(
            [
                (OrchestratorAction.REVIEW_TEST_POINTS, failed_review),
                (OrchestratorAction.REVISE_TEST_POINTS, revise),
            ]
        )
        service, repository = _create_service(orchestrator)
        state = TestAnalysisState("订单需求")
        state.test_points = [{"title": "提交订单"}]
        repository.create(TaskRecord(state=state, auto_run=True))

        failed = service.advance_task(state.task_id)
        revised = service.advance_task(state.task_id)

        self.assertFalse(failed.review_passed)
        self.assertEqual(revised.automatic_revision_count, 1)
        self.assertIsNone(revised.review_passed)

    def test_test_suggestion_feedback_stays_ready_for_revision(self):
        service, repository = _create_service()
        state = _seed_completed_task(repository)

        result = service.submit_feedback(
            state.task_id,
            SubmitFeedbackCommand(
                action="add",
                feedback_type="test_suggestion",
                target="新增测试点",
                content="增加优惠券并发核销场景",
                reason="历史缺陷",
            ),
        )

        self.assertEqual(
            result.human_feedback[0]["status"],
            FeedbackStatus.READY.value,
        )
        self.assertTrue(result.auto_run)

    def test_failed_node_records_metric_and_persists_state(self):
        def fail(state):
            state.fail("模型调用失败")
            raise RuntimeError("模型调用失败")

        service, _ = _create_service(
            ScriptedOrchestrator(
                [(OrchestratorAction.ANALYZE_REQUIREMENT, fail)]
            )
        )
        task = service.create_task(CreateTaskCommand(requirement="订单需求"))

        with self.assertRaises(RuntimeError):
            service.advance_task(task.task_id)

        failed = service.get_task(task.task_id)
        self.assertEqual(failed.status, AgentStatus.FAILED)
        self.assertEqual(len(failed.metrics), 1)
        self.assertFalse(failed.metrics[0].succeeded)
        self.assertEqual(failed.metrics[0].error_type, "RuntimeError")

    def test_unknown_task_returns_explicit_error(self):
        service, _ = _create_service()

        with self.assertRaises(TaskNotFoundError):
            service.get_task("missing-task")


if __name__ == "__main__":
    unittest.main()
