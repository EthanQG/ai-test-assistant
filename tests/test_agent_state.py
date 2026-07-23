import json
import unittest

from agent import (
    AgentEventType,
    AgentStatus,
    AgentStep,
    TestAnalysisState,
)


class TestAnalysisStateTests(unittest.TestCase):
    def test_new_task_has_initial_state_and_created_event(self):
        state = TestAnalysisState(requirement="  用户可以提交订单  ")

        self.assertEqual(state.requirement, "用户可以提交订单")
        self.assertEqual(state.status, AgentStatus.PENDING)
        self.assertEqual(state.current_step, AgentStep.INITIALIZE)
        self.assertEqual(len(state.events), 1)
        self.assertEqual(
            state.events[0].event_type,
            AgentEventType.TASK_CREATED,
        )

    def test_empty_requirement_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "requirement cannot be empty"):
            TestAnalysisState(requirement="  ")

    def test_step_lifecycle_is_recorded(self):
        state = TestAnalysisState(requirement="用户可以提交订单")

        state.start_step(
            AgentStep.ANALYZE_REQUIREMENT,
            "正在分析需求",
        )
        state.requirement_facts = ["用户可以提交订单"]
        state.complete_step(
            AgentStep.ANALYZE_REQUIREMENT,
            "需求分析完成",
            {"fact_count": 1},
        )

        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertEqual(
            [event.event_type for event in state.events],
            [
                AgentEventType.TASK_CREATED,
                AgentEventType.STEP_STARTED,
                AgentEventType.STEP_COMPLETED,
            ],
        )
        self.assertEqual(state.events[-1].data["fact_count"], 1)

    def test_cannot_complete_a_step_that_is_not_current(self):
        state = TestAnalysisState(requirement="用户可以提交订单")
        state.start_step(AgentStep.RETRIEVE_KNOWLEDGE, "检索知识")

        with self.assertRaisesRegex(ValueError, "cannot complete step"):
            state.complete_step(
                AgentStep.GENERATE_TEST_POINTS,
                "生成完成",
            )

    def test_task_can_wait_for_user_and_resume(self):
        state = TestAnalysisState(requirement="用户可以上传文件")
        state.start_step(AgentStep.ANALYZE_REQUIREMENT, "分析需求")

        state.wait_for_user(["允许上传哪些文件格式？"])
        self.assertEqual(state.status, AgentStatus.WAITING_FOR_USER)
        self.assertEqual(
            state.open_questions,
            ["允许上传哪些文件格式？"],
        )

        state.resume()
        self.assertEqual(state.status, AgentStatus.RUNNING)

    def test_waiting_task_must_be_resumed_before_next_step(self):
        state = TestAnalysisState(requirement="用户可以上传文件")
        state.start_step(AgentStep.ANALYZE_REQUIREMENT, "分析需求")
        state.wait_for_user(["允许上传哪些文件格式？"])

        with self.assertRaisesRegex(ValueError, "must be resumed first"):
            state.start_step(
                AgentStep.RETRIEVE_KNOWLEDGE,
                "检索知识",
            )

    def test_completed_task_is_terminal(self):
        state = TestAnalysisState(requirement="用户可以提交订单")
        state.complete("最终测试分析报告")

        self.assertEqual(state.status, AgentStatus.COMPLETED)
        self.assertEqual(state.current_step, AgentStep.FINALIZE)

        with self.assertRaisesRegex(ValueError, "already completed"):
            state.start_step(
                AgentStep.REVIEW_TEST_POINTS,
                "重新评审",
            )

    def test_failed_task_records_error(self):
        state = TestAnalysisState(requirement="用户可以提交订单")
        state.start_step(AgentStep.RETRIEVE_KNOWLEDGE, "检索知识")
        state.fail("Milvus connection failed")

        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertEqual(
            state.error_message,
            "Milvus connection failed",
        )
        self.assertEqual(
            state.events[-1].event_type,
            AgentEventType.TASK_FAILED,
        )

    def test_state_can_be_serialized_to_json(self):
        state = TestAnalysisState(requirement="用户可以提交订单")
        state.start_step(AgentStep.ANALYZE_REQUIREMENT, "分析需求")

        payload = state.to_dict()
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["current_step"], "analyze_requirement")
        self.assertIn("用户可以提交订单", serialized)
        self.assertIn("occurred_at", serialized)


if __name__ == "__main__":
    unittest.main()
