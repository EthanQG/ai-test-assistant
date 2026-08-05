from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence

import requests


@dataclass(frozen=True)
class OllamaEmbeddingSettings:
    base_url: str
    model: str
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "OllamaEmbeddingSettings":
        base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        ).strip().rstrip("/")
        model = os.getenv(
            "EMBEDDING_MODEL",
            "nomic-embed-text",
        ).strip()
        if not base_url:
            raise ValueError("OLLAMA_BASE_URL cannot be empty")
        if not model:
            raise ValueError("EMBEDDING_MODEL cannot be empty")
        return cls(
            base_url=base_url,
            model=model,
            timeout_seconds=_positive_int_env("EMBEDDING_TIMEOUT", 60),
        )


class OllamaBatchEmbeddingService:
    """Uses Ollama /api/embed once for a bounded batch of chunk texts."""

    def __init__(
        self,
        settings: OllamaEmbeddingSettings,
        *,
        session=requests,
    ):
        self._settings = settings
        self._session = session

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        cleaned = [text.strip() for text in texts]
        if not cleaned or any(not text for text in cleaned):
            raise ValueError("embedding texts must be non-empty")
        response = self._session.post(
            f"{self._settings.base_url}/api/embed",
            json={
                "model": self._settings.model,
                "input": cleaned,
                "truncate": False,
            },
            timeout=self._settings.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list):
            raise ValueError("Ollama response.embeddings must be a list")
        return embeddings


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value
