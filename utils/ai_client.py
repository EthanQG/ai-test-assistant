import json
import requests
from utils.config import ConfigManager


class DeepSeekClient:
    def __init__(self):
        self.config = ConfigManager()
        self._validate_config()

    def _validate_config(self):
        if not self.config.is_api_configured:
            raise ValueError("DEEPSEEK_API_KEY is not configured")

    def call(self, prompt: str, system_prompt: str = "") -> str:
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
            "stream": False
        }

        response = requests.post(
            f"{self.config.base_url}/chat/completions",
            headers=headers,
            json=payload
        )

        if response.status_code != 200:
            raise ValueError(f"API调用失败，状态码: {response.status_code}, 响应: {response.text}")

        result = response.json()
        return result["choices"][0]["message"]["content"].strip()

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
            stream=True
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