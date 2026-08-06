from collections.abc import Callable
import logging
from time import perf_counter
from typing import TypeVar

from utils.telemetry import (
    MetricErrorCategory,
    record_service_call,
    service_metric,
    utc_now,
)


StructuredResult = TypeVar("StructuredResult")
logger = logging.getLogger(__name__)
LARGE_STRUCTURED_OUTPUT_MAX_TOKENS = 8192


def generate_and_parse_json(
    llm_service,
    prompt: str,
    system_prompt: str,
    parser: Callable[[str], StructuredResult],
    max_attempts: int = 2,
    max_tokens: int | None = None,
) -> StructuredResult:
    """Generate structured JSON with one bounded retry on validation failure."""
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    started_at = utc_now()
    started_counter = perf_counter()
    last_error: Exception | None = None
    raw_response = ""
    try:
        for attempt in range(max_attempts):
            current_prompt = prompt
            if attempt:
                current_prompt += (
                    "\n\n上一次响应无法通过JSON或字段校验。"
                    "请重新生成一个完整、合法且严格符合字段要求的JSON对象，"
                    "不要输出解释。"
                )

            generate_json = getattr(llm_service, "generate_json", None)
            if callable(generate_json):
                if max_tokens is None:
                    raw_response = generate_json(
                        current_prompt,
                        system_prompt,
                    )
                else:
                    raw_response = generate_json(
                        current_prompt,
                        system_prompt,
                        max_tokens=max_tokens,
                    )
            else:
                raw_response = llm_service.generate(
                    current_prompt,
                    system_prompt,
                )

            try:
                result = parser(raw_response)
                record_service_call(
                    service_metric(
                        operation="structured_output_validation",
                        dependency="structured_output",
                        started_at=started_at,
                        started_counter=started_counter,
                        succeeded=True,
                        input_chars=len(prompt) + len(system_prompt),
                        output_chars=len(raw_response),
                        retry_count=attempt,
                    )
                )
                return result
            except ValueError as exc:
                last_error = exc
                logger.warning(
                    "Structured output validation failed "
                    "(attempt %s/%s): %s",
                    attempt + 1,
                    max_attempts,
                    exc,
                )
        raise last_error or ValueError("structured JSON generation failed")
    except Exception as exc:
        record_service_call(
            service_metric(
                operation="structured_output_validation",
                dependency="structured_output",
                started_at=started_at,
                started_counter=started_counter,
                succeeded=False,
                input_chars=len(prompt) + len(system_prompt),
                output_chars=len(raw_response),
                retry_count=(max_attempts - 1 if last_error else 0),
                error=exc,
                error_category=(
                    MetricErrorCategory.VALIDATION
                    if last_error is not None
                    else MetricErrorCategory.UNKNOWN
                ),
            )
        )
        raise
