import json
import unittest

from agent import (
    AgentEventType,
    AgentStatus,
    AgentStep,
    RequirementAnalysisError,
    RequirementAnalysisResult,
    RequirementAnalysisValidationError,
    RequirementAnalyzer,
    TestAnalysisState,
)


def valid_analysis_payload() -> dict:
    return {
        "summary": "用户提交订单并扣减库存",
        "modules": ["订单", "库存"],
        "requirement_facts": [
            "用户可以提交订单",
            "订单提交后扣减库存",
        ],
        "business_rules": ["库存不足时不能提交订单"],
        "state_transitions": ["待提交 -> 已提交：用户确认提交"],
        "inferred_risks": [
            {
                "risk": "重复提交可能重复扣减库存",
                "basis": "需求存在订单提交和库存扣减操作",
            }
        ],
        "open_questions": [],
    }


class FakeLLMService:
    def __init__(self, response: str = "", error: Exception | None = None):
        self.response = response
        self.error = error
        self.last_prompt = ""
        self.last_system_prompt = ""

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        if self.error:
            raise self.error
        return self.response


class RequirementAnalysisResultTests(unittest.TestCase):
    def test_valid_json_is_parsed(self):
        result = RequirementAnalysisResult.from_json(
            json.dumps(valid_analysis_payload(), ensure_ascii=False)
        )

        self.assertEqual(result.summary, "用户提交订单并扣减库存")
        self.assertEqual(result.modules, ["订单", "库存"])
        self.assertEqual(
            result.inferred_risks[0].basis,
            "需求存在订单提交和库存扣减操作",
        )

    def test_json_code_fence_is_tolerated(self):
        response = (
            "```json\n"
            + json.dumps(valid_analysis_payload(), ensure_ascii=False)
            + "\n```"
        )

        result = RequirementAnalysisResult.from_json(response)

        self.assertEqual(result.modules, ["订单", "库存"])

    def test_missing_required_field_is_rejected(self):
        payload = valid_analysis_payload()
        del payload["business_rules"]

        with self.assertRaisesRegex(
            RequirementAnalysisValidationError,
            "business_rules must be a list",
        ):
            RequirementAnalysisResult.from_json(
                json.dumps(payload, ensure_ascii=False)
            )

    def test_invalid_risk_shape_is_rejected(self):
        payload = valid_analysis_payload()
        payload["inferred_risks"] = [{"risk": "重复提交"}]

        with self.assertRaisesRegex(
            RequirementAnalysisValidationError,
            "basis must be a non-empty string",
        ):
            RequirementAnalysisResult.from_json(
                json.dumps(payload, ensure_ascii=False)
            )

    def test_unexpected_top_level_field_is_rejected(self):
        payload = valid_analysis_payload()
        payload["confidence"] = 0.98

        with self.assertRaisesRegex(
            RequirementAnalysisValidationError,
            "unexpected fields: confidence",
        ):
            RequirementAnalysisResult.from_json(
                json.dumps(payload, ensure_ascii=False)
            )


class RequirementAnalyzerTests(unittest.TestCase):
    def test_successful_analysis_updates_state_and_events(self):
        llm = FakeLLMService(
            json.dumps(valid_analysis_payload(), ensure_ascii=False)
        )
        analyzer = RequirementAnalyzer(llm_service=llm)
        state = TestAnalysisState(requirement="用户提交订单后扣减库存")

        result = analyzer.analyze(state)

        self.assertEqual(result.summary, "用户提交订单并扣减库存")
        self.assertEqual(state.requirement_summary, result.summary)
        self.assertEqual(state.modules, ["订单", "库存"])
        self.assertEqual(
            state.business_rules,
            ["库存不足时不能提交订单"],
        )
        self.assertEqual(
            state.state_transitions,
            ["待提交 -> 已提交：用户确认提交"],
        )
        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertEqual(
            state.current_step,
            AgentStep.ANALYZE_REQUIREMENT,
        )
        self.assertEqual(
            [event.event_type for event in state.events],
            [
                AgentEventType.TASK_CREATED,
                AgentEventType.STEP_STARTED,
                AgentEventType.STEP_COMPLETED,
            ],
        )
        self.assertIn(
            "用户提交订单后扣减库存",
            llm.last_prompt,
        )
        self.assertIn("只输出一个合法 JSON 对象", llm.last_system_prompt)

    def test_open_questions_put_task_in_waiting_state(self):
        payload = valid_analysis_payload()
        payload["open_questions"] = ["库存扣减失败后是否回滚订单？"]
        analyzer = RequirementAnalyzer(
            llm_service=FakeLLMService(
                json.dumps(payload, ensure_ascii=False)
            )
        )
        state = TestAnalysisState(requirement="用户提交订单后扣减库存")

        analyzer.analyze(state)

        self.assertEqual(state.status, AgentStatus.WAITING_FOR_USER)
        self.assertEqual(
            state.open_questions,
            ["库存扣减失败后是否回滚订单？"],
        )
        self.assertEqual(
            state.events[-2].event_type,
            AgentEventType.STEP_COMPLETED,
        )
        self.assertEqual(
            state.events[-1].event_type,
            AgentEventType.INFORMATION,
        )

    def test_invalid_json_fails_task(self):
        analyzer = RequirementAnalyzer(
            llm_service=FakeLLMService("not-json")
        )
        state = TestAnalysisState(requirement="用户提交订单")

        with self.assertRaises(RequirementAnalysisError):
            analyzer.analyze(state)

        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertIn("not valid JSON", state.error_message)
        self.assertEqual(
            state.events[-1].event_type,
            AgentEventType.TASK_FAILED,
        )

    def test_llm_error_fails_task(self):
        analyzer = RequirementAnalyzer(
            llm_service=FakeLLMService(
                error=TimeoutError("model timeout")
            )
        )
        state = TestAnalysisState(requirement="用户提交订单")

        with self.assertRaisesRegex(
            RequirementAnalysisError,
            "model timeout",
        ):
            analyzer.analyze(state)

        self.assertEqual(state.status, AgentStatus.FAILED)
        self.assertIn("model timeout", state.error_message)


if __name__ == "__main__":
    unittest.main()
