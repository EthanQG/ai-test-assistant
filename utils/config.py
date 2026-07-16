import os
from dotenv import load_dotenv


class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        load_dotenv()
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
        self.knowledge_base_path = os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge/bug_experience.txt")
        self.max_tokens = int(os.getenv("MAX_TOKENS", 4096))
        self.temperature = float(os.getenv("TEMPERATURE", 0.7))

    @property
    def is_api_configured(self) -> bool:
        return bool(self.api_key)