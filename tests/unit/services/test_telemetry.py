from datetime import datetime, timezone
from time import perf_counter
from types import SimpleNamespace

import pytest

from utils.telemetry import (
    MetricErrorCategory,
    ServiceCallMetric,
    TokenUsageSource,
    observed_service_call,
    provider_or_estimated_token_usage,
    record_service_call,
    service_metric,
    telemetry_scope,
)
from utils.ai_client import DeepSeekClient
from agent.structured_output import generate_and_parse_json


def test_telemetry_scope_adds_task_and_action_without_sensitive_payload():
    with telemetry_scope(task_id="task-1", action="review_test_points") as metrics:
        record_service_call(
            ServiceCallMetric(
                operation="chat_completion",
                dependency="llm",
                started_at=datetime.now(timezone.utc),
                duration_ms=25,
                succeeded=True,
                input_chars=120,
                output_chars=40,
                metadata={"finish_reason": "stop"},
            )
        )

    payload = metrics[0].to_dict()
    assert payload["task_id"] == "task-1"
    assert payload["action"] == "review_test_points"
    assert payload["duration_ms"] == 25
    assert "prompt" not in payload
    assert "api_key" not in payload


def test_provider_usage_is_preferred_over_estimation():
    usage = provider_or_estimated_token_usage(
        {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        input_text="不会使用该估算",
        output_text="不会使用该估算",
    )

    assert usage.source is TokenUsageSource.PROVIDER
    assert usage.input_tokens == 100
    assert usage.output_tokens == 20
    assert usage.total_tokens == 120


def test_missing_provider_usage_is_explicitly_estimated():
    usage = provider_or_estimated_token_usage(
        None,
        input_text="输入文本",
        output_text="output",
    )

    assert usage.source is TokenUsageSource.ESTIMATED
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0
    assert usage.total_tokens == usage.input_tokens + usage.output_tokens


def test_observed_service_call_records_failure_category():
    @observed_service_call(
        operation="search_chunks",
        dependency="milvus",
        error_category=MetricErrorCategory.MILVUS,
    )
    def fail():
        raise RuntimeError("unavailable")

    with telemetry_scope() as metrics:
        with pytest.raises(RuntimeError, match="unavailable"):
            fail()

    assert metrics[0].succeeded is False
    assert metrics[0].error_type == "RuntimeError"
    assert metrics[0].error_category is MetricErrorCategory.MILVUS


def test_service_metric_duration_is_non_negative():
    started_at = datetime.now(timezone.utc)
    started_counter = perf_counter()

    metric = service_metric(
        operation="parse_document",
        dependency="document_parser",
        started_at=started_at,
        started_counter=started_counter,
        succeeded=True,
    )

    assert metric.duration_ms >= 0
    assert metric.started_at.tzinfo is not None


def test_llm_client_records_provider_token_usage(monkeypatch):
    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"ok": true}'},
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 4,
                    "total_tokens": 16,
                },
            }

    monkeypatch.setattr("utils.ai_client.requests.post", lambda *args, **kwargs: Response())
    client = DeepSeekClient.__new__(DeepSeekClient)
    client.config = SimpleNamespace(
        api_key="secret-not-recorded",
        base_url="https://example.invalid",
        model="test-model",
        max_tokens=100,
        temperature=0,
        request_timeout=5,
    )

    with telemetry_scope(task_id="task-llm") as metrics:
        assert client.call("input", "system") == '{"ok": true}'

    payload = metrics[0].to_dict()
    assert payload["token_usage"] == {
        "input_tokens": 12,
        "output_tokens": 4,
        "total_tokens": 16,
        "source": "provider",
    }
    assert len(payload["metadata"]["prompt_fingerprint"]) == 16
    assert "secret-not-recorded" not in repr(payload)
    assert "system" not in repr(payload)


def test_structured_output_records_validation_retry_count():
    class FakeLLM:
        responses = iter(["invalid", '{"ok": true}'])

        def generate(self, prompt, system_prompt=""):
            del prompt, system_prompt
            return next(self.responses)

    def parser(payload):
        if payload == "invalid":
            raise ValueError("invalid JSON")
        return payload

    with telemetry_scope() as metrics:
        result = generate_and_parse_json(
            FakeLLM(),
            "prompt",
            "system",
            parser,
        )

    assert result == '{"ok": true}'
    validation = next(
        metric for metric in metrics if metric.dependency == "structured_output"
    )
    assert validation.succeeded is True
    assert validation.retry_count == 1
