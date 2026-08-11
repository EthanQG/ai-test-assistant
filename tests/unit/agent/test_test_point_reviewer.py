import json
import unittest

from agent.events import AgentEventType, AgentStep
from agent.review_models import (
    TestPointReviewResult,
    TestPointReviewValidationError,
)
from agent.state import AgentStatus, TestAnalysisState
from agent.test_point_reviewer import (
    TestPointReviewError,
    TestPointReviewer,
)


def review_payload(
    *,
    overall_score: int = 90,
    coverage_status: str = "covered",
    hallucinations: list | None = None,
) -> dict:
    return {
        "overall_score": overall_score,
        "dimension_scores": {
            "requirement_coverage": 95,
            "boundary_exception": 85,
            "executability": 90,
            "traceability": 90,
        },
        "requirement_coverage": [
            {
                "requirement_fact": "提交订单时扣减库存",
                "status": coverage_status,
                "covered_by": (
                    ["库存充足时提交订单"]
                    if coverage_status != "missing"
                    else []
                ),
                "gap": "" if coverage_status == "covered" else "缺少失败结果",
            }
        ],
        "missing_scenarios": [],
        "duplicate_groups": [],
        "hallucination_issues": hallucinations or [],
        "revision_suggestions": [],
    }


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
    state.requirement_summary = "订单库存"
    state.requirement_facts = ["提交订单时扣减库存"]
    state.business_rules = ["库存不足时不允许提交"]
    state.test_points = [
        {
            "title": "库存充足时提交订单",
            "category": "functional",
            "priority": "P0",
            "scenario": "库存充足时提交",
            "preconditions": ["库存为1"],
            "steps": ["提交订单"],
            "expected_results": ["提交成功", "库存为0"],
            "sources": ["requirement"],
            "source_refs": ["提交订单时扣减库存"],
        }
    ]
    return state


class TestPointReviewResultTests(unittest.TestCase):
    def test_valid_review_is_parsed(self):
        result = TestPointReviewResult.from_json(
            json.dumps(review_payload(), ensure_ascii=False)
        )
        self.assertEqual(result.overall_score, 90)
        self.assertEqual(result.uncovered_requirement_count, 0)

    def test_score_out_of_range_is_rejected(self):
        payload = review_payload(overall_score=101)
        with self.assertRaisesRegex(
            TestPointReviewValidationError,
            "between 0 and 100",
        ):
            TestPointReviewResult.from_json(json.dumps(payload))

    def test_unknown_top_level_field_is_rejected(self):
        payload = review_payload()
        payload["passed"] = True
        with self.assertRaisesRegex(
            TestPointReviewValidationError,
            "review result fields are invalid",
        ):
            TestPointReviewResult.from_json(json.dumps(payload))

    def test_single_title_duplicate_group_is_rejected(self):
        payload = review_payload()
        payload["duplicate_groups"] = [["库存充足时提交订单"]]
        with self.assertRaisesRegex(
            TestPointReviewValidationError,
            "at least two titles",
        ):
            TestPointReviewResult.from_json(json.dumps(payload))

    def test_blank_optional_issue_items_are_normalized(self):
        payload = review_payload()
        payload["missing_scenarios"] = ["", "  "]
        payload["revision_suggestions"] = ["", "补充边界场景"]

        result = TestPointReviewResult.from_json(
            json.dumps(payload, ensure_ascii=False)
        )

        self.assertEqual(result.missing_scenarios, [])
        self.assertEqual(
            result.revision_suggestions,
            ["补充边界场景"],
        )

    def test_supported_missing_scenario_object_is_normalized(self):
        payload = review_payload()
        payload["missing_scenarios"] = [
            {"scenario": "补充库存并发扣减场景"}
        ]

        result = TestPointReviewResult.from_json(
            json.dumps(payload, ensure_ascii=False)
        )

        self.assertEqual(
            result.missing_scenarios,
            ["补充库存并发扣减场景"],
        )

    def test_string_hallucination_is_conservatively_normalized(self):
        payload = review_payload()
        payload["hallucination_issues"] = ["测试点断言固定重试三次"]

        result = TestPointReviewResult.from_json(
            json.dumps(payload, ensure_ascii=False)
        )

        self.assertEqual(len(result.hallucination_issues), 1)
        self.assertEqual(
            result.hallucination_issues[0].test_point_title,
            "未指定测试点",
        )
        self.assertEqual(
            result.hallucination_issues[0].unsupported_claim,
            "测试点断言固定重试三次",
        )

    def test_unsupported_optional_issue_object_is_rejected(self):
        payload = review_payload()
        payload["missing_scenarios"] = [{"unknown": "场景"}]

        with self.assertRaisesRegex(
            TestPointReviewValidationError,
            "supported text object",
        ):
            TestPointReviewResult.from_json(
                json.dumps(payload, ensure_ascii=False)
            )


class TestPointReviewerTests(unittest.TestCase):
    def test_passing_review_updates_state_and_event(self):
        llm = FakeLLMService(
            json.dumps(review_payload(), ensure_ascii=False)
        )
        state = ready_state()

        result = TestPointReviewer(llm_service=llm).review(state)

        self.assertEqual(result.overall_score, 90)
        self.assertTrue(state.review_passed)
        self.assertEqual(state.review_threshold, 80)
        self.assertEqual(state.review_result["overall_score"], 90)
        self.assertEqual(state.current_step, AgentStep.REVIEW_TEST_POINTS)
        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertIn("提交订单时扣减库存", llm.calls[0][0])
        self.assertIn("库存充足时提交订单", llm.calls[0][0])
        self.assertTrue(llm.calls[0][1])
        self.assertEqual(llm.received_max_tokens, [16384])
        self.assertEqual(
            state.events[-1].event_type,
            AgentEventType.STEP_COMPLETED,
        )
        self.assertTrue(state.events[-1].data["passed"])
        self.assertEqual(len(state.review_history), 1)
        self.assertTrue(state.review_history[0]["passed"])
        self.assertEqual(
            state.review_history[0]["result"]["overall_score"],
            90,
        )

    def test_score_below_threshold_does_not_pass(self):
        llm = FakeLLMService(json.dumps(review_payload(overall_score=79)))
        state = ready_state()

        TestPointReviewer(llm_service=llm).review(state)

        self.assertFalse(state.review_passed)

    def test_fact_ids_are_restored_to_original_facts_before_saving(self):
        payload = review_payload()
        payload["requirement_coverage"][0]["requirement_fact"] = "F001"
        state = ready_state()

        result = TestPointReviewer(
            llm_service=FakeLLMService(json.dumps(payload))
        ).review(state)

        self.assertEqual(
            result.requirement_coverage[0].requirement_fact,
            "提交订单时扣减库存",
        )
        self.assertEqual(
            state.review_result["requirement_coverage"][0][
                "requirement_fact"
            ],
            "提交订单时扣减库存",
        )

    def test_max_tokens_truncation_retries_only_the_reviewer_once(self):
        class TruncatedOnceLLM(FakeLLMService):
            def generate_json(
                self,
                prompt: str,
                system_prompt: str,
                max_tokens: int | None = None,
            ) -> str:
                self.received_max_tokens.append(max_tokens)
                self.calls.append((prompt, system_prompt))
                if len(self.calls) == 1:
                    raise ValueError(
                        "LLM输出达到max_tokens限制，结构化JSON被截断"
                    )
                return json.dumps(review_payload(), ensure_ascii=False)

        llm = TruncatedOnceLLM()
        state = ready_state()

        result = TestPointReviewer(llm_service=llm).review(state)

        self.assertEqual(result.overall_score, 90)
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("只返回完整紧凑JSON", llm.calls[1][0])
        self.assertEqual(llm.received_max_tokens, [16384, 16384])

    def test_partial_coverage_does_not_pass(self):
        llm = FakeLLMService(
            json.dumps(review_payload(coverage_status="partial"))
        )
        state = ready_state()

        TestPointReviewer(llm_service=llm).review(state)

        self.assertFalse(state.review_passed)

    def test_hallucination_issue_does_not_pass(self):
        issue = {
            "test_point_title": "库存充足时提交订单",
            "issue": "包含未定义的冻结规则",
            "unsupported_claim": "失败后冻结用户",
        }
        llm = FakeLLMService(
            json.dumps(review_payload(hallucinations=[issue]))
        )
        state = ready_state()

        TestPointReviewer(llm_service=llm).review(state)

        self.assertFalse(state.review_passed)

    def test_string_hallucination_issue_does_not_pass(self):
        payload = review_payload(
            hallucinations=["测试点包含没有依据的固定重试次数"]
        )
        state = ready_state()

        TestPointReviewer(
            llm_service=FakeLLMService(json.dumps(payload))
        ).review(state)

        self.assertFalse(state.review_passed)

    def test_missing_coverage_fact_fails_task(self):
        payload = review_payload()
        payload["requirement_coverage"] = []
        llm = FakeLLMService(json.dumps(payload))
        state = ready_state()

        with self.assertRaises(TestPointReviewError):
            TestPointReviewer(llm_service=llm).review(state)

        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertIn("every requirement fact", state.error_message)

    def test_test_points_are_required_without_calling_llm(self):
        llm = FakeLLMService(json.dumps(review_payload()))
        state = ready_state()
        state.test_points = []

        with self.assertRaisesRegex(
            TestPointReviewError,
            "must be generated first",
        ):
            TestPointReviewer(llm_service=llm).review(state)

        self.assertEqual(llm.calls, [])
        self.assertEqual(state.status, AgentStatus.PENDING)

    def test_invalid_response_fails_task(self):
        llm = FakeLLMService('{"overall_score": 90}')
        state = ready_state()

        with self.assertRaises(TestPointReviewError):
            TestPointReviewer(llm_service=llm).review(state)

        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertEqual(
            state.events[-1].event_type,
            AgentEventType.TASK_FAILED,
        )

    def test_llm_error_fails_task(self):
        llm = FakeLLMService(error=TimeoutError("评审模型超时"))
        state = ready_state()

        with self.assertRaises(TestPointReviewError):
            TestPointReviewer(llm_service=llm).review(state)

        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertIn("评审模型超时", state.error_message)

    def test_invalid_passing_score_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            TestPointReviewer(passing_score=101)


if __name__ == "__main__":
    unittest.main()
