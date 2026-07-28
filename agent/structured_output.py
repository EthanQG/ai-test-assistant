from collections.abc import Callable
import logging
from typing import TypeVar


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

    last_error: Exception | None = None
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
            return parser(raw_response)
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
