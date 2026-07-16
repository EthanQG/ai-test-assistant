import requests
from utils.config import (
    get_deepseek_api_key,
    get_deepseek_base_url,
    get_deepseek_model,
    get_max_tokens,
    get_temperature,
)


def call_ai(prompt: str, system_prompt: str = "你是一个资深测试工程师助手，擅长分析需求、生成测试点和测试用例。") -> str:
    api_key = get_deepseek_api_key()
    base_url = get_deepseek_base_url()
    model = get_deepseek_model()
    max_tokens = get_max_tokens()
    temperature = get_temperature()

    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False
    }

    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload
    )

    if response.status_code != 200:
        raise ValueError(f"API调用失败，状态码: {response.status_code}, 响应: {response.text}")

    result = response.json()
    return result["choices"][0]["message"]["content"].strip()


def call_ai_stream(
    prompt: str,
    system_prompt: str = "你是一个资深测试工程师助手，擅长分析需求、生成测试点和测试用例。"
):
    api_key = get_deepseek_api_key()
    base_url = get_deepseek_base_url()
    model = get_deepseek_model()
    max_tokens = get_max_tokens()
    temperature = get_temperature()

    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True
    }

    response = requests.post(
        f"{base_url}/chat/completions",
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
                    import json
                    chunk = json.loads(line_str)
                    content = chunk["choices"][0]["delta"].get("content", "")
                    if content:
                        yield content
            except Exception:
                continue