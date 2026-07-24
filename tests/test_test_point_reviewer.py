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

    def generate(self, prompt: str, system_prompt: str) -> str:
        self.calls.append((prompt, system_prompt))
        if self.error:
            raise self.error
        return self.response


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
