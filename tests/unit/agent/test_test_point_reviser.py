import json
import unittest

from agent.events import AgentEventType, AgentStep
from agent.human_feedback import HumanFeedbackHandler
from agent.state import AgentStatus, TestAnalysisState
from agent.test_point_reviser import (
    TestPointReviser,
    TestPointRevisionError,
)


def make_test_point(
    title: str,
    expected_results: list[str],
) -> dict:
    return {
        "title": title,
        "category": "functional",
        "priority": "P0",
        "scenario": "验证库存不足时订单不可提交",
        "preconditions": ["商品库存为0"],
        "steps": ["用户提交订单"],
        "expected_results": expected_results,
        "sources": ["requirement"],
        "source_refs": ["库存不足时不允许提交"],
    }


def ready_state() -> TestAnalysisState:
    state = TestAnalysisState("库存不足时不允许提交订单")
    state.requirement_summary = "订单库存校验"
    state.requirement_facts = ["库存不足时不允许提交订单"]
    state.business_rules = ["库存不足时不允许提交"]
    state.test_points = [
        make_test_point("库存不足时提交订单", ["订单提交失败"])
    ]
    state.review_result = {
        "overall_score": 70,
        "missing_scenarios": ["缺少明确的库存不变预期"],
        "duplicate_groups": [],
        "hallucination_issues": [],
        "revision_suggestions": ["补充库存不被扣减的预期"],
    }
    state.review_passed = False
    return state


def revised_response() -> str:
    return json.dumps(
        {
            "operations": [
                {
                    "action": "replace",
                    "target_title": "库存不足时提交订单",
                    "test_point": make_test_point(
                        "库存不足时提交订单",
                        ["订单提交失败", "商品库存保持为0"],
                    ),
                }
            ]
        },
        ensure_ascii=False,
    )


class FakeLLMService:
    def __init__(self, response: str = "", error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls = []
        self.received_max_tokens = []

    def generate(self, prompt: str, system_prompt: str) -> str:
        self.calls.append((prompt, system_prompt))
        if self.error:
            raise self.error
        return self.response

    def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int | None = None,
    ) -> str:
        self.received_max_tokens.append(max_tokens)
        return self.generate(prompt, system_prompt)


class SequenceLLMService(FakeLLMService):
    def __init__(self, responses: list[str]):
        super().__init__()
        self.responses = iter(responses)

    def generate(self, prompt: str, system_prompt: str) -> str:
        self.calls.append((prompt, system_prompt))
        return next(self.responses)


class TestPointReviserTests(unittest.TestCase):
    def test_success_updates_points_and_invalidates_review(self):
        llm = FakeLLMService(revised_response())
        state = ready_state()

        result = TestPointReviser(llm_service=llm).revise(state)

        self.assertEqual(len(result.test_points), 1)
        self.assertIn(
            "商品库存保持为0",
            state.test_points[0]["expected_results"],
        )
        self.assertEqual(state.revision_count, 1)
        self.assertEqual(state.automatic_revision_count, 1)
        self.assertEqual(state.human_revision_count, 0)
        self.assertIsNone(state.review_passed)
        self.assertEqual(state.review_result["overall_score"], 70)
        self.assertEqual(state.current_step, AgentStep.REVISE_TEST_POINTS)
        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertIn("补充库存不被扣减的预期", llm.calls[0][0])
        self.assertIn("库存不足时提交订单", llm.calls[0][0])
        self.assertTrue(llm.calls[0][1])
        self.assertEqual(llm.received_max_tokens, [8192])
        self.assertEqual(
            state.events[-1].event_type,
            AgentEventType.STEP_COMPLETED,
        )
        self.assertTrue(
            state.events[-1].data["review_invalidated"]
        )
        self.assertEqual(
            state.events[-1].data["operation_count"],
            1,
        )
        self.assertEqual(len(state.revision_history), 1)
        self.assertEqual(
            state.revision_history[0]["before_test_points"][0][
                "expected_results"
            ],
            ["订单提交失败"],
        )

    def test_passing_review_cannot_be_revised(self):
        llm = FakeLLMService(revised_response())
        state = ready_state()
        state.review_passed = True

        with self.assertRaisesRegex(
            TestPointRevisionError,
            "must not be revised automatically",
        ):
            TestPointReviser(llm_service=llm).revise(state)

        self.assertEqual(llm.calls, [])
        self.assertEqual(state.status, AgentStatus.PENDING)

    def test_completed_review_is_required(self):
        llm = FakeLLMService(revised_response())
        state = ready_state()
        state.review_result = None
        state.review_passed = None

        with self.assertRaisesRegex(
            TestPointRevisionError,
            "failed review or ready human feedback is required",
        ):
            TestPointReviser(llm_service=llm).revise(state)

        self.assertEqual(llm.calls, [])

    def test_unchanged_response_fails_task(self):
        state = ready_state()
        llm = FakeLLMService(
            json.dumps(
                {
                    "operations": [
                        {
                            "action": "replace",
                            "target_title": "库存不足时提交订单",
                            "test_point": state.test_points[0],
                        }
                    ]
                }
            )
        )

        with self.assertRaises(TestPointRevisionError):
            TestPointReviser(llm_service=llm).revise(state)

        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertIn("did not change", state.error_message)
        self.assertEqual(state.revision_count, 0)

    def test_invalid_response_fails_without_replacing_points(self):
        llm = FakeLLMService('{"operations": []}')
        state = ready_state()
        original = list(state.test_points)

        with self.assertRaises(TestPointRevisionError):
            TestPointReviser(llm_service=llm).revise(state)

        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertEqual(state.test_points, original)
        self.assertEqual(
            state.events[-1].event_type,
            AgentEventType.TASK_FAILED,
        )

    def test_delta_revision_preserves_untouched_points(self):
        state = ready_state()
        state.test_points.append(
            make_test_point("库存充足时提交订单", ["订单提交成功"])
        )

        TestPointReviser(
            llm_service=FakeLLMService(revised_response())
        ).revise(state)

        self.assertEqual(len(state.test_points), 2)
        self.assertEqual(
            state.test_points[1]["title"],
            "库存充足时提交订单",
        )

    def test_duplicate_add_is_retried_inside_atomic_merge_boundary(self):
        state = ready_state()
        duplicate = json.dumps(
            {
                "operations": [
                    {
                        "action": "add",
                        "test_point": state.test_points[0],
                    }
                ]
            },
            ensure_ascii=False,
        )
        llm = SequenceLLMService([duplicate, revised_response()])

        result = TestPointReviser(llm_service=llm).revise(state)

        self.assertEqual(len(llm.calls), 2)
        self.assertIn("上一次响应无法通过", llm.calls[1][0])
        self.assertEqual(len(result.test_points), 1)
        self.assertIn(
            "商品库存保持为0",
            result.test_points[0].expected_results,
        )
        self.assertEqual(state.revision_count, 1)
        self.assertEqual(state.status, AgentStatus.RUNNING)

    def test_invalid_target_fails_atomically(self):
        state = ready_state()
        original = json.loads(json.dumps(state.test_points))
        response = json.dumps(
            {
                "operations": [
                    {
                        "action": "remove",
                        "target_title": "不存在的测试点",
                    }
                ]
            },
            ensure_ascii=False,
        )

        with self.assertRaises(TestPointRevisionError):
            TestPointReviser(
                llm_service=FakeLLMService(response)
            ).revise(state)

        self.assertEqual(state.test_points, original)
        self.assertEqual(state.revision_count, 0)

    def test_llm_error_fails_task(self):
        llm = FakeLLMService(error=TimeoutError("修正模型超时"))
        state = ready_state()

        with self.assertRaises(TestPointRevisionError):
            TestPointReviser(llm_service=llm).revise(state)

        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertIn("修正模型超时", state.error_message)

    def test_ready_human_feedback_can_revise_passing_result(self):
        llm = FakeLLMService(revised_response())
        state = ready_state()
        state.review_passed = True
        HumanFeedbackHandler().submit(
            state,
            {
                "action": "modify",
                "feedback_type": "test_suggestion",
                "target": "库存不足时提交订单",
                "content": "补充库存保持不变的预期",
                "reason": "需要验证失败操作没有副作用",
            },
        )

        TestPointReviser(llm_service=llm).revise(state)

        self.assertIn("补充库存保持不变的预期", llm.calls[0][0])
        self.assertNotIn("补充库存不被扣减的预期", llm.calls[0][0])
        self.assertIn("operations 最多返回 1 项", llm.calls[0][0])
        self.assertEqual(state.automatic_revision_count, 0)
        self.assertEqual(state.human_revision_count, 1)
        self.assertEqual(
            state.human_feedback[0]["status"],
            "applied",
        )
        self.assertEqual(
            state.events[-1].data["applied_feedback_count"],
            1,
        )

    def test_human_feedback_cannot_expand_revision_scope(self):
        state = ready_state()
        state.review_passed = True
        HumanFeedbackHandler().submit(
            state,
            {
                "action": "remove",
                "feedback_type": "test_suggestion",
                "target": "库存不足时提交订单",
                "content": "删除这个测试点",
                "reason": "该场景不再适用",
            },
        )
        original = json.loads(json.dumps(state.test_points))

        with self.assertRaises(TestPointRevisionError):
            TestPointReviser(
                llm_service=FakeLLMService(revised_response())
            ).revise(state)

        self.assertEqual(state.test_points, original)
        self.assertEqual(state.revision_count, 0)

    def test_unconfirmed_business_rule_cannot_trigger_revision(self):
        llm = FakeLLMService(revised_response())
        state = ready_state()
        state.review_result = None
        state.review_passed = None
        HumanFeedbackHandler().submit(
            state,
            {
                "action": "add",
                "feedback_type": "business_rule",
                "target": "库存业务规则",
                "content": "库存不足时允许创建缺货订单",
                "reason": "用户提出新的业务处理方式",
            },
        )

        with self.assertRaisesRegex(
            TestPointRevisionError,
            "failed review or ready human feedback is required",
        ):
            TestPointReviser(llm_service=llm).revise(state)

        self.assertEqual(llm.calls, [])


if __name__ == "__main__":
    unittest.main()
