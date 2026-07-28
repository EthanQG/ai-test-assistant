import json
import unittest

from agent.structured_output import generate_and_parse_json


class SequenceLLMService:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def generate_json(self, prompt, system_prompt):
        self.prompts.append((prompt, system_prompt))
        return self.responses.pop(0)


class StructuredOutputTests(unittest.TestCase):
    def test_invalid_json_is_retried_once(self):
        llm = SequenceLLMService(
            ['{"summary": "未闭合}', '{"summary": "有效"}']
        )

        result = generate_and_parse_json(
            llm,
            "返回JSON",
            "系统规则",
            json.loads,
        )

        self.assertEqual(result["summary"], "有效")
        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("上一次响应无法通过", llm.prompts[1][0])

    def test_transport_error_is_not_blindly_retried(self):
        class FailedLLM:
            calls = 0

            def generate_json(self, prompt, system_prompt):
                self.calls += 1
                raise RuntimeError("network unavailable")

        llm = FailedLLM()
        with self.assertRaisesRegex(RuntimeError, "network unavailable"):
            generate_and_parse_json(
                llm,
                "返回JSON",
                "系统规则",
                json.loads,
            )
        self.assertEqual(llm.calls, 1)
