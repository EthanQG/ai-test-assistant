import os
from dotenv import load_dotenv

load_dotenv()


def get_deepseek_api_key() -> str:
    return os.getenv("DEEPSEEK_API_KEY", "")


def get_deepseek_base_url() -> str:
    return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


def get_deepseek_model() -> str:
    return os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")


def get_knowledge_base_path() -> str:
    return os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge/bug_experience.txt")


def get_max_tokens() -> int:
    return int(os.getenv("MAX_TOKENS", 4096))


def get_temperature() -> float:
    return float(os.getenv("TEMPERATURE", 0.7))


def is_api_configured() -> bool:
    return bool(get_deepseek_api_key())