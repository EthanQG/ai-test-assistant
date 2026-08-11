import json
import re
import unittest

import pytest

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


def clarification_candidate(
    question: str,
    category: str = "core_rule",
) -> dict:
    return {
        "question": question,
        "category": category,
        "blocking_reason": "不确认将无法判断核心业务结果",
        "evidence": "当前需求缺少对应规则",
    }


class FakeLLMService:
    def __init__(self, response: str = "", error: Exception | None = None):
        self.response = response
        self.error = error
        self.last_prompt = ""
        self.last_system_prompt = ""
        self.received_max_tokens = []
        self.prompts = []

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.response

    def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> str:
        self.received_max_tokens.append(max_tokens)
        return self.generate(prompt, system_prompt)


class TruncateOnceLLMService(FakeLLMService):
    def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> str:
        self.received_max_tokens.append(max_tokens)
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            raise ValueError(
                "LLM输出达到max_tokens限制，结构化JSON被截断"
            )
        return self.response


class CompactFlowLLMService(FakeLLMService):
    def __init__(self, *, truncate_first: bool = False):
        super().__init__()
        self.truncate_first = truncate_first

    def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> str:
        self.received_max_tokens.append(max_tokens)
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        self.prompts.append(prompt)
        if self.truncate_first and len(self.prompts) == 1:
            raise ValueError(
                "LLM输出达到max_tokens限制，结构化JSON被截断"
            )
        statement_ids = list(dict.fromkeys(
            re.findall(r'"id":"(S\d+)"', prompt)
        ))
        if "缺口审核专家" in system_prompt:
            return json.dumps(
                {
                    "open_questions": [
                        {
                            "question": "支付与关闭并发时哪个状态优先？",
                            "category": "flow_branch",
                            "blocking_reason": "无法确定最终订单状态",
                            "evidence_ids": [statement_ids[0]],
                        }
                    ]
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "summary": "订单规则",
                "modules": ["订单"],
                "fact_ids": statement_ids,
                "business_rule_ids": statement_ids[:1],
                "state_transition_ids": [],
                "inferred_risks": [
                    {
                        "risk": "重复请求可能重复处理",
                        "basis_ids": statement_ids[:1],
                    }
                ],
            },
            ensure_ascii=False,
        )


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

    def test_more_than_ten_open_question_candidates_are_rejected(self):
        payload = valid_analysis_payload()
        payload["open_questions"] = [
            clarification_candidate(f"问题{index}")
            for index in range(11)
        ]

        with self.assertRaisesRegex(
            RequirementAnalysisValidationError,
            "at most 10",
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
        self.assertIn("requirement_facts最多40项", llm.last_system_prompt)
        self.assertEqual(llm.received_max_tokens, [8192])

    def test_truncated_chunk_is_split_and_retried_with_bounded_children(self):
        llm = CompactFlowLLMService(truncate_first=True)
        analyzer = RequirementAnalyzer(llm_service=llm)
        state = TestAnalysisState(
            requirement="# 订单规则\n" + ("库存不足时拒绝创建订单。" * 200)
        )

        result = analyzer.analyze(state)

        assert len(llm.prompts) >= 3
        assert result.requirement_facts
        completed = state.events[-2]
        assert completed.data["requirement_analysis_attempt_count"] == len(
            llm.prompts
        )
        assert completed.data["requirement_adaptive_split_count"] == 1

    def test_non_truncation_error_does_not_trigger_adaptive_split(self):
        llm = FakeLLMService(error=TimeoutError("model timeout"))
        analyzer = RequirementAnalyzer(llm_service=llm)
        state = TestAnalysisState(
            requirement="# 订单规则\n" + ("库存不足时拒绝创建订单。" * 70)
        )

        with pytest.raises(RequirementAnalysisError, match="model timeout"):
            analyzer.analyze(state)

        assert len(llm.prompts) == 1

    def test_long_requirement_is_chunked_and_merged_without_duplicates(self):
        llm = CompactFlowLLMService()
        analyzer = RequirementAnalyzer(llm_service=llm)
        state = TestAnalysisState(
            requirement="".join(
                f"## {index}. 章节{index}\n" + ("订单业务规则。" * 90)
                for index in range(1, 4)
            )
        )

        result = analyzer.analyze(state)

        assert len(llm.received_max_tokens) > 1
        assert set(llm.received_max_tokens) == {4096}
        assert result.requirement_facts
        assert len(result.inferred_risks) == 1
        assert result.inferred_risks[0].basis.startswith("[S001｜")
        assert state.open_questions == ["支付与关闭并发时哪个状态优先？"]
        assert "S001" in llm.prompts[0]
        assert state.events[-2].data["requirement_chunked"] is True
        assert state.events[-2].data["requirement_chunk_count"] > 1
        assert state.events[-2].data["requirement_compact_contract"] is True
        assert state.events[-2].data["requirement_statement_count"] > 1

    def test_chunk_failure_identifies_source_and_fails_whole_task(self):
        analyzer = RequirementAnalyzer(
            llm_service=FakeLLMService("not-json")
        )
        state = TestAnalysisState(
            requirement="# 第一章\n" + ("库存规则。" * 400)
        )

        with pytest.raises(
            RequirementAnalysisError,
            match="compact statement analysis failed",
        ):
            analyzer.analyze(state)

        assert state.status is AgentStatus.FAILED
        assert "compact statement analysis failed" in state.error_message

    def test_open_questions_put_task_in_waiting_state(self):
        payload = valid_analysis_payload()
        payload["open_questions"] = [
            clarification_candidate("库存扣减失败后是否回滚订单？")
        ]
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

    def test_waiting_task_can_be_reanalyzed_with_answers_and_deferred_items(self):
        llm = FakeLLMService(
            json.dumps(valid_analysis_payload(), ensure_ascii=False)
        )
        analyzer = RequirementAnalyzer(llm_service=llm)
        state = TestAnalysisState(requirement="用户可以使用优惠券")
        questions = ["优惠券是否允许叠加？", "优惠券失效时间如何计算？"]
        state.wait_for_user(questions)

        analyzer.reanalyze_with_clarifications(
            state,
            {
                questions[0]: "不允许叠加",
                questions[1]: None,
            },
        )

        self.assertEqual(
            state.user_clarifications,
            [{"question": questions[0], "answer": "不允许叠加"}],
        )
        self.assertEqual(state.deferred_questions, [questions[1]])
        self.assertEqual(state.open_questions, [])
        self.assertEqual(state.status, AgentStatus.RUNNING)
        self.assertIn("不允许叠加", llm.last_prompt)
        self.assertIn(questions[1], llm.last_prompt)

    def test_clarification_answers_must_match_current_questions(self):
        analyzer = RequirementAnalyzer(
            llm_service=FakeLLMService(
                json.dumps(valid_analysis_payload(), ensure_ascii=False)
            )
        )
        state = TestAnalysisState(requirement="用户可以使用优惠券")
        state.wait_for_user(["优惠券是否允许叠加？"])

        with self.assertRaisesRegex(
            RequirementAnalysisError,
            "must match all current open questions",
        ):
            analyzer.reanalyze_with_clarifications(
                state,
                {"另一个问题": "不允许"},
            )

    def test_deferred_question_is_not_asked_again(self):
        payload = valid_analysis_payload()
        payload["open_questions"] = [
            clarification_candidate(
                "优惠券失效时间如何计算？", "critical_value"
            )
        ]
        analyzer = RequirementAnalyzer(
            llm_service=FakeLLMService(
                json.dumps(payload, ensure_ascii=False)
            )
        )
        state = TestAnalysisState(requirement="用户可以使用优惠券")
        state.deferred_questions = ["优惠券失效时间如何计算？"]

        result = analyzer.analyze(state)

        self.assertEqual(result.open_questions, [])
        self.assertEqual(state.open_questions, [])
        self.assertEqual(state.status, AgentStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
