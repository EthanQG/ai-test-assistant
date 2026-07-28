import json
from typing import Any

import requests
from utils.config import ConfigManager


class DeepSeekClient:
    def __init__(self):
        self.config = ConfigManager()
        self._validate_config()

    def _validate_config(self):
        if not self.config.is_api_configured:
            raise ValueError("DEEPSEEK_API_KEY is not configured")

    def call(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: dict[str, str] | None = None,
        max_tokens: int | None = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": False
        }
        if response_format is not None:
            payload["response_format"] = response_format

        response = requests.post(
            f"{self.config.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.config.request_timeout,
        )

        if response.status_code != 200:
            raise ValueError(f"API调用失败，状态码: {response.status_code}, 响应: {response.text}")

        result = response.json()
        return self._extract_content(result)

    def call_stream(self, prompt: str, system_prompt: str = ""):
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": True
        }

        response = requests.post(
            f"{self.config.base_url}/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=self.config.request_timeout,
        )

        if response.status_code != 200:
            raise ValueError(f"API调用失败，状态码: {response.status_code}, 响应: {response.text}")

        for line in response.iter_lines():
            if line:
                try:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data: "):
                        line_str = line_str[6:]
                        if line_str == "[DONE]":
                            break
                        chunk = json.loads(line_str)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
                except Exception:
                    continue

    @staticmethod
    def _extract_content(result: dict[str, Any]) -> str:
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("LLM响应缺少choices")

        choice = choices[0]
        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            raise ValueError(
                "LLM输出达到max_tokens限制，结构化JSON被截断"
            )

        message = choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "LLM返回空内容"
                + (
                    f"（finish_reason={finish_reason}）"
                    if finish_reason
                    else ""
                )
            )
        return content.strip()
