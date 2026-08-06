from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
import math
import re
from time import perf_counter
from typing import Any, Iterator


class MetricErrorCategory(str, Enum):
    TIMEOUT = "timeout"
    TRANSPORT = "transport"
    OUTPUT_TRUNCATED = "output_truncated"
    VALIDATION = "validation"
    INPUT_BUDGET = "input_budget"
    DOCUMENT_PARSE = "document_parse"
    OCR = "ocr"
    VISION = "vision"
    EMBEDDING = "embedding"
    MILVUS = "milvus"
    UNKNOWN = "unknown"


class TokenUsageSource(str, Enum):
    PROVIDER = "provider"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    source: TokenUsageSource

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "source": self.source.value,
        }


@dataclass(frozen=True)
class ServiceCallMetric:
    operation: str
    dependency: str
    started_at: datetime
    duration_ms: int
    succeeded: bool
    task_id: str | None = None
    action: str | None = None
    model: str | None = None
    input_chars: int | None = None
    output_chars: int | None = None
    token_usage: TokenUsage | None = None
    retry_count: int = 0
    error_type: str | None = None
    error_category: MetricErrorCategory | None = None
    metadata: dict[str, Any] | None = None

    def with_task_id(self, task_id: str) -> "ServiceCallMetric":
        return replace(self, task_id=self.task_id or task_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "dependency": self.dependency,
            "started_at": self.started_at.isoformat(),
            "duration_ms": self.duration_ms,
            "succeeded": self.succeeded,
            "task_id": self.task_id,
            "action": self.action,
            "model": self.model,
            "input_chars": self.input_chars,
            "output_chars": self.output_chars,
            "token_usage": (
                None if self.token_usage is None else self.token_usage.to_dict()
            ),
            "retry_count": self.retry_count,
            "error_type": self.error_type,
            "error_category": (
                None
                if self.error_category is None
                else self.error_category.value
            ),
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class TelemetryContext:
    task_id: str | None = None
    action: str | None = None


_ACTIVE_METRICS: ContextVar[list[ServiceCallMetric] | None] = ContextVar(
    "active_service_call_metrics",
    default=None,
)
_ACTIVE_CONTEXT: ContextVar[TelemetryContext] = ContextVar(
    "active_telemetry_context",
    default=TelemetryContext(),
)


@contextmanager
def telemetry_scope(
    *,
    task_id: str | None = None,
    action: str | None = None,
) -> Iterator[list[ServiceCallMetric]]:
    metrics: list[ServiceCallMetric] = []
    metrics_token = _ACTIVE_METRICS.set(metrics)
    context_token = _ACTIVE_CONTEXT.set(
        TelemetryContext(task_id=task_id, action=action)
    )
    try:
        yield metrics
    finally:
        _ACTIVE_CONTEXT.reset(context_token)
        _ACTIVE_METRICS.reset(metrics_token)


def record_service_call(metric: ServiceCallMetric) -> None:
    metrics = _ACTIVE_METRICS.get()
    if metrics is None:
        return
    context = _ACTIVE_CONTEXT.get()
    metrics.append(
        replace(
            metric,
            task_id=metric.task_id or context.task_id,
            action=metric.action or context.action,
        )
    )


def observed_service_call(
    *,
    operation: str,
    dependency: str,
    error_category: MetricErrorCategory,
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            started_at = utc_now()
            started_counter = perf_counter()
            try:
                result = func(*args, **kwargs)
                record_service_call(
                    service_metric(
                        operation=operation,
                        dependency=dependency,
                        started_at=started_at,
                        started_counter=started_counter,
                        succeeded=True,
                    )
                )
                return result
            except Exception as exc:
                record_service_call(
                    service_metric(
                        operation=operation,
                        dependency=dependency,
                        started_at=started_at,
                        started_counter=started_counter,
                        succeeded=False,
                        error=exc,
                        error_category=error_category,
                    )
                )
                raise

        return wrapper

    return decorator


def service_metric(
    *,
    operation: str,
    dependency: str,
    started_at: datetime,
    started_counter: float,
    succeeded: bool,
    model: str | None = None,
    input_chars: int | None = None,
    output_chars: int | None = None,
    token_usage: TokenUsage | None = None,
    retry_count: int = 0,
    error: Exception | None = None,
    error_category: MetricErrorCategory | None = None,
    metadata: dict[str, Any] | None = None,
) -> ServiceCallMetric:
    return ServiceCallMetric(
        operation=operation,
        dependency=dependency,
        started_at=started_at,
        duration_ms=max(0, round((perf_counter() - started_counter) * 1000)),
        succeeded=succeeded,
        model=model,
        input_chars=input_chars,
        output_chars=output_chars,
        token_usage=token_usage,
        retry_count=retry_count,
        error_type=None if error is None else type(error).__name__,
        error_category=error_category,
        metadata=metadata,
    )


def provider_or_estimated_token_usage(
    usage: Any,
    *,
    input_text: str,
    output_text: str,
) -> TokenUsage:
    if isinstance(usage, dict):
        input_tokens = _non_negative_int(usage.get("prompt_tokens"))
        output_tokens = _non_negative_int(usage.get("completion_tokens"))
        total_tokens = _non_negative_int(usage.get("total_tokens"))
        if input_tokens is not None and output_tokens is not None:
            return TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=(
                    total_tokens
                    if total_tokens is not None
                    else input_tokens + output_tokens
                ),
                source=TokenUsageSource.PROVIDER,
            )
    input_tokens = estimate_tokens(input_text)
    output_tokens = estimate_tokens(output_text)
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        source=TokenUsageSource.ESTIMATED,
    )


def estimate_tokens(text: str) -> int:
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", text))
    non_cjk = len(re.sub(r"[\u3400-\u9fff\s]", "", text))
    return cjk_count + math.ceil(non_cjk / 4)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value
