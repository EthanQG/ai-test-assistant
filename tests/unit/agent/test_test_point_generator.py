import json
import unittest

from agent.events import AgentEventType, AgentStep
from agent.models import (
    TestPointCategory,
    TestPointGenerationResult,
    TestPointPriority,
    TestPointRevisionPlan,
    TestPointSource,
    TestPointValidationError,
)
from agent.state import AgentStatus, KnowledgeRetrievalStatus, TestAnalysisState
from agent.test_point_generator import TestPointGenerationError, TestPointGenerator


def valid_response() -> str:
    return json.dumps(
        {
            "test_points": [
                {
                    "title": "库存充足时提交订单",
                    "category": "functional",
                    "priority": "P0",
                    "scenario": "验证库存充足时订单可以提交",
                    "preconditions": ["商品库存为 1"],
                    "steps": ["用户提交包含该商品的订单"],
                    "expected_results": ["订单提交成功", "商品库存扣减为 0"],
                    "sources": ["requirement", "historical_asset"],
                    "source_refs": [
                        "提交订单时需要扣减库存",
                        "历史资产中的重复扣减防范思路",
                    ],
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


def ready_state() -> TestAnalysisState:
    state = TestAnalysisState("用户提交订单时扣减库存")
    state.requirement_summary = "订单提交与库存扣减"
    state.modules = ["订单", "库存"]
    state.requirement_facts = ["提交订单时需要扣减库存"]
    state.business_rules = ["库存不足时不允许提交"]
    state.inferred_risks = [
        {"risk": "重复提交可能重复扣减", "basis": "存在提交和扣减操作"}
    ]
    state.rag_context = "历史资产中的重复扣减防范思路"
    state.knowledge_retrieval_status = KnowledgeRetrievalStatus.MATCHED
    return state


class TestPointGenerationResultTests(unittest.TestCase):
    def test_valid_json_is_parsed(self):
        result = TestPointGenerationResult.from_json(valid_response())
        self.assertEqual(len(result.test_points), 1)
        self.assertEqual(result.test_points[0].category, TestPointCategory.FUNCTIONAL)
        self.assertEqual(result.test_points[0].priority, TestPointPriority.P0)

    def test_empty_test_points_are_rejected(self):
        with self.assertRaisesRegex(TestPointValidationError, "non-empty list"):
            TestPointGenerationResult.from_json('{"test_points": []}')

    def test_invalid_category_is_rejected(self):
        payload = json.loads(valid_response())
        payload["test_points"][0]["category"] = "security"
        with self.assertRaisesRegex(TestPointValidationError, "category must be"):
            TestPointGenerationResult.from_json(json.dumps(payload))

    def test_unknown_field_is_rejected(self):
        payload = json.loads(valid_response())
        payload["test_points"][0]["confidence"] = 0.9
        with self.assertRaisesRegex(
            TestPointValidationError,
            "unexpected test point fields",
        ):
            TestPointGenerationResult.from_json(json.dumps(payload))

    def test_source_provenance_aliases_are_normalized_and_deduplicated(self):
        payload = json.loads(valid_response())
        payload["test_points"][0]["sources"] = [
            "requirement_fact",
            "inferred_risk",
            "rag",
            "local_bug_knowledge",
            "user_clarification",
        ]

        result = TestPointGenerationResult.from_json(json.dumps(payload))

        self.assertEqual(
            result.test_points[0].sources,
            [
                TestPointSource.REQUIREMENT,
                TestPointSource.HISTORICAL_ASSET,
                TestPointSource.TEST_EXPERIENCE,
                TestPointSource.USER_FEEDBACK,
            ],
        )

    def test_unknown_source_is_rejected_with_its_value(self):
        payload = json.loads(valid_response())
        payload["test_points"][0]["sources"] = ["internet_guess"]

        with self.assertRaisesRegex(
            TestPointValidationError,
            "internet_guess",
        ):
            TestPointGenerationResult.from_json(json.dumps(payload))

    def test_empty_steps_are_rejected(self):
        payload = json.loads(valid_response())
        payload["test_points"][0]["steps"] = []
        with self.assertRaisesRegex(
            TestPointValidationError,
            "steps must be a non-empty list",
        ):
            TestPointGenerationResult.from_json(json.dumps(payload))


class TestPointRevisionPlanTests(unittest.TestCase):
    def test_add_replace_and_remove_are_applied_in_order(self):
        current = json.loads(valid_response())["test_points"]
        replacement = dict(current[0])
        replacement["expected_results"] = [
            "订单提交成功",
            "库存只扣减一次",
        ]
        added = dict(current[0])
        added["title"] = "重复提交订单"
        plan = TestPointRevisionPlan.from_json(
            json.dumps(
                {
                    "operations": [
                        {
                            "action": "replace",
                            "target_title": "库存充足时提交订单",
                            "test_point": replacement,
                        },
                        {
                            "action": "add",
                            "test_point": added,
                        },
                        {
                            "action": "remove",
                            "target_title": "重复提交订单",
                        },
                    ]
                },
                ensure_ascii=False,
            )
        )

        result = plan.apply_to(current)

        self.assertEqual(len(result.test_points), 1)
        self.assertEqual(
            result.test_points[0].expected_results,
            ["订单提交成功", "库存只扣减一次"],
        )

    def test_unknown_operation_field_is_rejected(self):
        current = json.loads(valid_response())["test_points"][0]
        response = json.dumps(
            {
                "operations": [
                    {
                        "action": "add",
                        "target_title": "不应出现",
                        "test_point": current,
                    }
                ]
            },
            ensure_ascii=False,
        )

        with self.assertRaisesRegex(
            TestPointValidationError,
            "add operation must contain only",
        ):
            TestPointRevisionPlan.from_json(response)


class TestPointGeneratorTests(unittest.TestCase):
    def test_success_updates_state_and_events(self):
        llm = FakeLLMService(valid_response())
        state = ready_state()
        result = TestPointGenerator(llm_service=llm).generate(state)

        self.assertEqual(len(result.test_points), 1)
        self.assertEqual(len(state.test_points), 1)
        self.assertEqual(state.current_step, AgentStep.GENERATE_TEST_POINTS)
        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertIn("订单提交与库存扣减", llm.calls[0][0])
        self.assertIn("历史资产中的重复扣减防范思路", llm.calls[0][0])
        self.assertTrue(llm.calls[0][1])
        self.assertEqual(llm.received_max_tokens, [8192])
        self.assertEqual(state.events[-1].event_type, AgentEventType.STEP_COMPLETED)
        self.assertEqual(
            state.events[-1].data["category_counts"],
            {"functional": 1},
        )

    def test_no_match_can_still_generate(self):
        llm = FakeLLMService(valid_response())
        state = ready_state()
        state.rag_context = ""
        state.knowledge_retrieval_status = KnowledgeRetrievalStatus.NO_MATCH
        TestPointGenerator(llm_service=llm).generate(state)
        self.assertEqual(len(state.test_points), 1)

    def test_degraded_retrieval_can_still_generate(self):
        llm = FakeLLMService(valid_response())
        state = ready_state()
        state.rag_context = ""
        state.knowledge_retrieval_status = KnowledgeRetrievalStatus.DEGRADED
        TestPointGenerator(llm_service=llm).generate(state)
        self.assertEqual(len(state.test_points), 1)

    def test_retrieval_must_be_attempted(self):
        llm = FakeLLMService(valid_response())
        state = ready_state()
        state.knowledge_retrieval_status = KnowledgeRetrievalStatus.NOT_STARTED
        with self.assertRaisesRegex(
            TestPointGenerationError,
            "knowledge retrieval must be attempted",
        ):
            TestPointGenerator(llm_service=llm).generate(state)
        self.assertEqual(llm.calls, [])
        self.assertEqual(state.status, AgentStatus.PENDING)

    def test_open_questions_block_generation(self):
        llm = FakeLLMService(valid_response())
        state = ready_state()
        state.open_questions = ["库存并发规则是什么？"]
        with self.assertRaisesRegex(
            TestPointGenerationError,
            "open questions must be resolved",
        ):
            TestPointGenerator(llm_service=llm).generate(state)
        self.assertEqual(llm.calls, [])

    def test_invalid_llm_response_fails_task(self):
        llm = FakeLLMService('{"test_points": []}')
        state = ready_state()
        with self.assertRaises(TestPointGenerationError):
            TestPointGenerator(llm_service=llm).generate(state)
        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertEqual(state.events[-1].event_type, AgentEventType.TASK_FAILED)
        self.assertEqual(state.test_points, [])

    def test_llm_error_fails_task(self):
        llm = FakeLLMService(error=TimeoutError("模型超时"))
        state = ready_state()
        with self.assertRaises(TestPointGenerationError):
            TestPointGenerator(llm_service=llm).generate(state)
        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertIn("模型超时", state.error_message)


if __name__ == "__main__":
    unittest.main()
