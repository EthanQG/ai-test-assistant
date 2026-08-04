import os
import unittest

from dotenv import load_dotenv

from agent import (
    AgentStatus,
    AgentStep,
    OrchestratorAction,
    OrchestratorDecision,
    TestAnalysisState,
)
from application import (
    CreateTaskCommand,
    SubmitClarificationsCommand,
    TaskRecord,
    TaskSnapshotSerializer,
    TestAnalysisApplicationService,
)
from repositories import (
    MySQLSettings,
    MySQLTaskRepository,
    TaskNotFoundError,
    build_mysql_connection_factory,
)


RUN_MYSQL_INTEGRATION_TESTS = (
    os.getenv("RUN_MYSQL_INTEGRATION_TESTS", "").strip() == "1"
)


class _ClarificationOrchestrator:
    def __init__(self):
        self.resume_calls = 0

    def resume_with_clarifications(self, state, answers):
        self.resume_calls += 1
        questions = list(state.open_questions)
        state.resume()
        state.user_clarifications.extend(
            {
                "question": question,
                "answer": answers[question],
            }
            for question in questions
        )
        state.open_questions = []
        state.requirement_summary = "补充后可继续分析的脱敏需求"
        return OrchestratorDecision(
            OrchestratorAction.ANALYZE_REQUIREMENT,
            "通过编排器恢复需求分析",
        )

    def decide_next(self, state):
        del state
        return OrchestratorDecision(
            OrchestratorAction.RETRIEVE_KNOWLEDGE,
            "需求信息已充分，继续检索历史资产",
        )


class _WaitingRequirementOrchestrator:
    def __init__(self, question):
        self.question = question
        self.run_calls = 0

    def run_next(self, state):
        self.run_calls += 1
        state.wait_for_user([self.question])
        return OrchestratorDecision(
            OrchestratorAction.ANALYZE_REQUIREMENT,
            "需求分析发现需要用户补充的信息",
        )

    def decide_next(self, state):
        del state
        return OrchestratorDecision(
            OrchestratorAction.WAIT_FOR_USER,
            "等待用户补充信息",
        )


@unittest.skipUnless(
    RUN_MYSQL_INTEGRATION_TESTS,
    "set RUN_MYSQL_INTEGRATION_TESTS=1 to run real MySQL tests",
)
class MySQLTaskRepositoryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        cls.connection_factory = staticmethod(
            build_mysql_connection_factory(MySQLSettings.from_env())
        )
        cls._repository().initialize_schema()

    def setUp(self):
        self.created_task_ids = []

    def tearDown(self):
        repository = self._repository()
        for task_id in reversed(self.created_task_ids):
            try:
                repository.delete(task_id)
            except TaskNotFoundError:
                pass

    @classmethod
    def _repository(cls):
        return MySQLTaskRepository(
            cls.connection_factory,
            TaskSnapshotSerializer,
        )

    def _create(self, record):
        self.created_task_ids.append(record.state.task_id)
        self._repository().create(record)

    def test_real_mysql_crud_persists_snapshot_events_and_version(self):
        state = TestAnalysisState("集成测试：订单创建时校验库存")
        state.requirement_summary = "订单库存校验"
        record = TaskRecord(
            state=state,
            auto_run=True,
            next_action=OrchestratorAction.ANALYZE_REQUIREMENT.value,
        )
        self._create(record)

        restored = self._repository().get(state.task_id)
        self.assertIsInstance(restored, TaskRecord)
        self.assertEqual(restored.state.task_id, state.task_id)
        self.assertEqual(restored.state.requirement_summary, "订单库存校验")
        self.assertIsInstance(restored.state.status, AgentStatus)
        self.assertIsInstance(restored.state.current_step, AgentStep)

        restored.state.start_step(
            AgentStep.ANALYZE_REQUIREMENT,
            "集成测试开始需求分析",
        )
        restored.state.complete_step(
            AgentStep.ANALYZE_REQUIREMENT,
            "集成测试完成需求分析",
        )
        self._repository().save(restored)

        saved = self._repository().get(state.task_id)
        self.assertEqual(len(saved.state.events), 3)
        self.assertEqual(
            saved.state.events[-1].message,
            "集成测试完成需求分析",
        )
        self.assertIn(
            state.task_id,
            [item.state.task_id for item in self._repository().list()],
        )

        task_row, event_count = self._database_counts(state.task_id)
        self.assertEqual(int(task_row["version"]), 2)
        self.assertEqual(int(task_row["event_count"]), 3)
        self.assertEqual(event_count, 3)

        self._repository().delete(state.task_id)
        self.created_task_ids.remove(state.task_id)
        with self.assertRaises(TaskNotFoundError):
            self._repository().get(state.task_id)
        _, event_count = self._database_counts(state.task_id)
        self.assertEqual(event_count, 0)

    def test_new_application_service_restores_waiting_task_and_continues(self):
        question = "优惠券是否允许叠加？"
        waiting_orchestrator = _WaitingRequirementOrchestrator(question)
        first_service = TestAnalysisApplicationService(
            self._repository(),
            orchestrator_factory=lambda: waiting_orchestrator,
            knowledge_loader=lambda: "",
        )
        created = first_service.create_task(
            CreateTaskCommand(requirement="集成测试：优惠券使用规则")
        )
        self.created_task_ids.append(created.task_id)
        waiting = first_service.advance_task(created.task_id)
        first_service.submit_clarifications(
            created.task_id,
            SubmitClarificationsCommand({question: "不允许叠加"}),
        )

        orchestrator = _ClarificationOrchestrator()
        restarted_service = TestAnalysisApplicationService(
            self._repository(),
            orchestrator_factory=lambda: orchestrator,
            knowledge_loader=lambda: "",
        )
        before_resume = restarted_service.get_task(created.task_id)
        resumed = restarted_service.advance_task(created.task_id)

        self.assertEqual(waiting_orchestrator.run_calls, 1)
        self.assertEqual(waiting.status, AgentStatus.WAITING_FOR_USER)
        self.assertEqual(before_resume.task_id, created.task_id)
        self.assertTrue(before_resume.has_pending_clarifications)
        self.assertEqual(orchestrator.resume_calls, 1)
        self.assertEqual(resumed.task_id, created.task_id)
        self.assertEqual(resumed.status, AgentStatus.RUNNING)
        self.assertFalse(resumed.has_pending_clarifications)
        self.assertEqual(
            resumed.next_action,
            OrchestratorAction.RETRIEVE_KNOWLEDGE.value,
        )
        self.assertEqual(
            resumed.user_clarifications[-1]["answer"],
            "不允许叠加",
        )

    def test_new_application_service_restores_terminal_tasks_without_execution(
        self,
    ):
        completed = TestAnalysisState("集成测试：已完成任务")
        completed.complete("# 已完成的脱敏报告")
        failed = TestAnalysisState("集成测试：失败任务")
        failed.fail("集成测试模拟错误")

        records = [
            TaskRecord(
                state=completed,
                auto_run=False,
                next_action=OrchestratorAction.TERMINAL.value,
            ),
            TaskRecord(
                state=failed,
                auto_run=False,
                next_action=OrchestratorAction.TERMINAL.value,
            ),
        ]
        for record in records:
            self._create(record)

        def fail_if_orchestrator_is_created():
            raise AssertionError("terminal task must not create orchestrator")

        restarted_service = TestAnalysisApplicationService(
            self._repository(),
            orchestrator_factory=fail_if_orchestrator_is_created,
            knowledge_loader=lambda: "",
        )
        completed_view = restarted_service.advance_task(completed.task_id)
        failed_view = restarted_service.advance_task(failed.task_id)

        self.assertEqual(completed_view.status, AgentStatus.COMPLETED)
        self.assertEqual(completed_view.report, "# 已完成的脱敏报告")
        self.assertIsNone(completed_view.final_result)
        self.assertEqual(failed_view.status, AgentStatus.FAILED)
        self.assertEqual(
            failed_view.error_message,
            "集成测试模拟错误",
        )

    def _database_counts(self, task_id):
        connection = self.connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT version, event_count
                FROM agent_tasks
                WHERE task_id = %s
                """,
                (task_id,),
            )
            task_row = cursor.fetchone()
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM agent_task_events
                WHERE task_id = %s
                """,
                (task_id,),
            )
            event_count = int(cursor.fetchone()["count"])
            return task_row, event_count
        finally:
            cursor.close()
            connection.close()


if __name__ == "__main__":
    unittest.main()
