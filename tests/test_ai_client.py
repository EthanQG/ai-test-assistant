import unittest
from types import SimpleNamespace
from unittest.mock import patch

from utils.ai_client import DeepSeekClient


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._payload


def client_without_environment() -> DeepSeekClient:
    client = DeepSeekClient.__new__(DeepSeekClient)
    client.config = SimpleNamespace(
        api_key="test-key",
        base_url="https://example.invalid",
        model="test-model",
        max_tokens=4096,
        temperature=0.1,
        request_timeout=30,
    )
    return client


class DeepSeekClientTests(unittest.TestCase):
    @patch("utils.ai_client.requests.post")
    def test_json_response_format_is_sent(self, post):
        post.return_value = FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"ok": true}'},
                    }
                ]
            }
        )
        client = client_without_environment()

        content = client.call(
            "返回JSON",
            "系统规则",
            response_format={"type": "json_object"},
        )

        self.assertEqual(content, '{"ok": true}')
        payload = post.call_args.kwargs["json"]
        self.assertEqual(
            payload["response_format"],
            {"type": "json_object"},
        )
        self.assertEqual(post.call_args.kwargs["timeout"], 30)

    @patch("utils.ai_client.requests.post")
    def test_call_can_override_max_tokens_for_large_json(self, post):
        post.return_value = FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"ok": true}'},
                    }
                ]
            }
        )
        client = client_without_environment()

        client.call("返回较大的JSON", max_tokens=8192)

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["max_tokens"], 8192)

    def test_length_finish_reason_is_reported_as_truncation(self):
        result = {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": '{"summary": "partial'},
                }
            ]
        }

        with self.assertRaisesRegex(ValueError, "JSON被截断"):
            DeepSeekClient._extract_content(result)

    def test_empty_content_is_rejected(self):
        result = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": ""},
                }
            ]
        }

        with self.assertRaisesRegex(ValueError, "LLM返回空内容"):
            DeepSeekClient._extract_content(result)


if __name__ == "__main__":
    unittest.main()
