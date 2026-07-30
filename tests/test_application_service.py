import unittest

from agent import (
    AgentOrchestrator,
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
    def __init__(self, steps, clarification_callback=None):
        self.steps = list(steps)
        self.run_calls = 0
        self.clarification_calls = 0
        self.clarification_callback = (
            clarification_callback or _resume_clarifications
        )

    def decide_next(self, state):
        del state
        action = (
            self.steps[0][0]
            if self.steps
            else OrchestratorAction.TERMINAL
        )
        return OrchestratorDecision(action, "脚本化决策")

    def run_next(self, state):
        self.run_calls += 1
        action, callback = self.steps.pop(0)
        callback(state)
        return OrchestratorDecision(
            action,
            "脚本化决策",
            duration_seconds=0.01,
        )

    def resume_with_clarifications(self, state, answers):
        self.clarification_calls += 1
        self.clarification_callback(state, answers)
        return OrchestratorDecision(
            OrchestratorAction.ANALYZE_REQUIREMENT,
            "通过Orchestrator重新分析需求",
            duration_seconds=0.01,
        )


def _resume_clarifications(state, answers):
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
        orchestrator = ScriptedOrchestrator([])
        service, repository = _create_service(orchestrator)
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
        self.assertEqual(orchestrator.clarification_calls, 1)
        self.assertEqual(resumed.task_id, state.task_id)
        self.assertEqual(resumed.status, AgentStatus.RUNNING)
        self.assertFalse(resumed.has_pending_clarifications)
        self.assertEqual(resumed.open_questions, [])
        self.assertEqual(
            resumed.user_clarifications[0]["answer"],
            "最多叠加两张",
        )

    def test_incomplete_clarifications_do_not_call_orchestrator(self):
        orchestrator = ScriptedOrchestrator([])
        service, repository = _create_service(orchestrator)
        state = TestAnalysisState("用户可以使用优惠券")
        running = TestAnalysisState("仍在分析的需求")
        state.wait_for_user(
            ["优惠券是否允许叠加？", "优惠券何时失效？"]
        )
        repository.create(TaskRecord(state=state))
        repository.create(TaskRecord(state=running))

        with self.assertRaises(ValueError):
            service.submit_clarifications(
                running.task_id,
                SubmitClarificationsCommand(
                    {"优惠券是否允许叠加？": "允许"}
                ),
            )
        with self.assertRaises(ValueError):
            service.submit_clarifications(
                state.task_id,
                SubmitClarificationsCommand(
                    {"优惠券是否允许叠加？": "允许"}
                ),
            )
        with self.assertRaises(ValueError):
            service.submit_clarifications(
                state.task_id,
                SubmitClarificationsCommand(
                    {
                        "优惠券是否允许叠加？": "允许",
                        "优惠券何时失效？": "   ",
                    }
                ),
            )

        self.assertEqual(orchestrator.clarification_calls, 0)
        self.assertFalse(
            service.get_task(state.task_id).has_pending_clarifications
        )

    def test_reanalysis_can_wait_for_user_again_without_reusing_answers(self):
        def wait_again(state, answers):
            self.assertEqual(
                answers,
                {"优惠券是否允许叠加？": "暂不支持叠加"},
            )
            state.resume()
            state.open_questions = []
            state.requirement_summary = "补充后的优惠券需求"
            state.wait_for_user(["退款后优惠券是否返还？"])

        orchestrator = ScriptedOrchestrator(
            [],
            clarification_callback=wait_again,
        )
        service, repository = _create_service(orchestrator)
        state = TestAnalysisState("用户可以使用优惠券")
        state.wait_for_user(["优惠券是否允许叠加？"])
        repository.create(TaskRecord(state=state))
        service.submit_clarifications(
            state.task_id,
            SubmitClarificationsCommand(
                {"优惠券是否允许叠加？": "暂不支持叠加"}
            ),
        )

        waiting_again = service.advance_task(state.task_id)
        unchanged = service.advance_task(state.task_id)

        self.assertEqual(waiting_again.status, AgentStatus.WAITING_FOR_USER)
        self.assertEqual(
            waiting_again.open_questions,
            ["退款后优惠券是否返还？"],
        )
        self.assertFalse(waiting_again.has_pending_clarifications)
        self.assertEqual(unchanged.task_id, state.task_id)
        self.assertEqual(orchestrator.clarification_calls, 1)
        self.assertEqual(orchestrator.run_calls, 0)

    def test_failed_reanalysis_is_saved_and_answers_are_consumed_once(self):
        class FailingAnalyzer:
            def __init__(self):
                self.calls = 0

            def reanalyze_with_clarifications(self, state, _answers):
                self.calls += 1
                state.resume()
                state.fail("重新分析失败")
                raise RuntimeError("重新分析失败")

        analyzer = FailingAnalyzer()
        orchestrator = AgentOrchestrator(
            requirement_analyzer=analyzer,
        )
        service, repository = _create_service(orchestrator)
        state = TestAnalysisState("用户可以使用优惠券")
        state.wait_for_user(["优惠券是否允许叠加？"])
        repository.create(TaskRecord(state=state))
        service.submit_clarifications(
            state.task_id,
            SubmitClarificationsCommand(
                {"优惠券是否允许叠加？": "不允许"}
            ),
        )

        with self.assertRaises(RuntimeError):
            service.advance_task(state.task_id)

        failed = service.get_task(state.task_id)
        self.assertEqual(failed.status, AgentStatus.FAILED)
        self.assertFalse(failed.has_pending_clarifications)
        self.assertEqual(analyzer.calls, 1)
        self.assertFalse(failed.metrics[-1].succeeded)

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

    def test_in_progress_and_terminal_tasks_do_not_execute_nodes(self):
        orchestrator = ScriptedOrchestrator([])
        service, repository = _create_service(orchestrator)
        running = TestAnalysisState("执行中的任务")
        completed = TestAnalysisState("已完成任务")
        completed.complete("已完成报告")
        repository.create(
            TaskRecord(
                state=running,
                auto_run=True,
                in_progress=True,
            )
        )
        repository.create(TaskRecord(state=completed, auto_run=False))

        in_progress = service.advance_task(running.task_id)
        terminal = service.advance_task(completed.task_id)

        self.assertTrue(in_progress.in_progress)
        self.assertEqual(terminal.status, AgentStatus.COMPLETED)
        self.assertEqual(orchestrator.run_calls, 0)
        self.assertEqual(orchestrator.clarification_calls, 0)

    def test_retry_task_success_and_illegal_state(self):
        service, repository = _create_service()
        failed = TestAnalysisState("失败后重试的需求")
        failed.fail("模型服务失败")
        active = TestAnalysisState("仍在执行的需求")
        repository.create(TaskRecord(state=failed))
        repository.create(TaskRecord(state=active))

        retried = service.retry_task(failed.task_id)

        self.assertNotEqual(retried.task_id, failed.task_id)
        self.assertEqual(retried.requirement, failed.requirement)
        self.assertEqual(retried.status, AgentStatus.PENDING)
        with self.assertRaises(ValueError):
            service.retry_task(active.task_id)

    def test_list_and_delete_tasks(self):
        service, _ = _create_service()
        first = service.create_task(CreateTaskCommand(requirement="需求一"))
        second = service.create_task(CreateTaskCommand(requirement="需求二"))

        self.assertEqual(
            {task.task_id for task in service.list_tasks()},
            {first.task_id, second.task_id},
        )

        service.delete_task(first.task_id)

        self.assertEqual(
            [task.task_id for task in service.list_tasks()],
            [second.task_id],
        )
        with self.assertRaises(TaskNotFoundError):
            service.get_task(first.task_id)

    def test_complete_fake_flow_runs_all_nodes_through_orchestrator(self):
        calls = []

        class Analyzer:
            def analyze(self, state):
                calls.append("analyze")
                state.start_step(
                    AgentStep.ANALYZE_REQUIREMENT,
                    "分析需求",
                )
                state.requirement_summary = "订单需求"
                state.complete_step(
                    AgentStep.ANALYZE_REQUIREMENT,
                    "需求分析完成",
                )
                state.wait_for_user(["库存不足时是否允许下单？"])

            def reanalyze_with_clarifications(self, state, answers):
                calls.append("reanalyze")
                state.user_clarifications.append(
                    {
                        "question": "库存不足时是否允许下单？",
                        "answer": answers[
                            "库存不足时是否允许下单？"
                        ],
                    }
                )
                state.open_questions = []
                state.resume()
                state.start_step(
                    AgentStep.ANALYZE_REQUIREMENT,
                    "重新分析需求",
                )
                state.requirement_summary = "补充后的订单需求"
                state.requirement_facts = ["库存不足时禁止下单"]
                state.complete_step(
                    AgentStep.ANALYZE_REQUIREMENT,
                    "需求重新分析完成",
                )

        class Retriever:
            def retrieve(self, state):
                calls.append("retrieve")
                state.start_step(
                    AgentStep.RETRIEVE_KNOWLEDGE,
                    "检索知识",
                )
                state.knowledge_retrieval_status = (
                    KnowledgeRetrievalStatus.NO_MATCH
                )
                state.complete_step(
                    AgentStep.RETRIEVE_KNOWLEDGE,
                    "知识检索完成",
                )

        class Generator:
            def generate(self, state):
                calls.append("generate")
                state.start_step(
                    AgentStep.GENERATE_TEST_POINTS,
                    "生成测试点",
                )
                state.test_points = [{"title": "库存不足禁止下单"}]
                state.complete_step(
                    AgentStep.GENERATE_TEST_POINTS,
                    "测试点生成完成",
                )

        class Reviewer:
            def review(self, state):
                calls.append("review")
                state.start_step(
                    AgentStep.REVIEW_TEST_POINTS,
                    "评审测试点",
                )
                state.review_result = {"overall_score": 90}
                state.review_passed = True
                state.complete_step(
                    AgentStep.REVIEW_TEST_POINTS,
                    "测试点评审完成",
                )

        class FinalizerNode:
            def finalize(self, state):
                calls.append("finalize")
                state.start_step(AgentStep.FINALIZE, "整理报告")
                state.complete("# 订单测试分析报告")

        class UnexpectedReviser:
            def revise(self, state):
                del state
                raise AssertionError("reviser should not be called")

        orchestrator = AgentOrchestrator(
            requirement_analyzer=Analyzer(),
            knowledge_retriever=Retriever(),
            test_point_generator=Generator(),
            test_point_reviewer=Reviewer(),
            test_point_reviser=UnexpectedReviser(),
            finalizer=FinalizerNode(),
        )
        service, _ = _create_service(orchestrator)

        task = service.create_task(
            CreateTaskCommand(requirement="用户提交订单")
        )
        waiting = service.advance_task(task.task_id)
        service.submit_clarifications(
            task.task_id,
            SubmitClarificationsCommand(
                {"库存不足时是否允许下单？": "不允许"}
            ),
        )
        resumed = service.advance_task(task.task_id)
        retrieved = service.advance_task(task.task_id)
        generated = service.advance_task(task.task_id)
        reviewed = service.advance_task(task.task_id)
        completed = service.advance_task(task.task_id)

        self.assertEqual(waiting.status, AgentStatus.WAITING_FOR_USER)
        self.assertEqual(resumed.task_id, task.task_id)
        self.assertEqual(
            retrieved.knowledge_retrieval_status,
            KnowledgeRetrievalStatus.NO_MATCH,
        )
        self.assertEqual(len(generated.test_points), 1)
        self.assertTrue(reviewed.review_passed)
        self.assertEqual(completed.status, AgentStatus.COMPLETED)
        self.assertEqual(
            calls,
            [
                "analyze",
                "reanalyze",
                "retrieve",
                "generate",
                "review",
                "finalize",
            ],
        )
        self.assertEqual(
            [decision.action for decision in completed.decisions],
            [
                OrchestratorAction.ANALYZE_REQUIREMENT,
                OrchestratorAction.ANALYZE_REQUIREMENT,
                OrchestratorAction.RETRIEVE_KNOWLEDGE,
                OrchestratorAction.GENERATE_TEST_POINTS,
                OrchestratorAction.REVIEW_TEST_POINTS,
                OrchestratorAction.FINALIZE,
            ],
        )

    def test_unknown_task_returns_explicit_error(self):
        service, _ = _create_service()

        with self.assertRaises(TaskNotFoundError):
            service.get_task("missing-task")


if __name__ == "__main__":
    unittest.main()
