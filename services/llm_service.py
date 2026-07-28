from collections.abc import Iterator

from utils.ai_client import DeepSeekClient


class LLMService:
    """Application-facing wrapper around the configured language model client."""

    def __init__(self, client: DeepSeekClient | None = None):
        self._client = client

    def _get_client(self) -> DeepSeekClient:
        if self._client is None:
            self._client = DeepSeekClient()
        return self._client

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return self._get_client().call(prompt, system_prompt)

    def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> str:
        return self._get_client().call(
            prompt,
            system_prompt,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> Iterator[str]:
        yield from self._get_client().call_stream(prompt, system_prompt)
