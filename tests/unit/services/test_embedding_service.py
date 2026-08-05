from unittest.mock import patch

import pytest

from services.embedding_service import (
    OllamaBatchEmbeddingService,
    OllamaEmbeddingSettings,
)


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.raise_calls = 0

    def raise_for_status(self):
        self.raise_calls += 1

    def json(self):
        return self.payload


class _FakeSession:
    def __init__(self, payload):
        self.response = _FakeResponse(payload)
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append((url, json, timeout))
        return self.response


def test_ollama_embedding_service_uses_one_batch_request():
    session = _FakeSession({"embeddings": [[0.1, 0.2], [0.3, 0.4]]})
    service = OllamaBatchEmbeddingService(
        OllamaEmbeddingSettings("http://ollama", "nomic", 12),
        session=session,
    )

    vectors = service.embed_batch(["事实一", "规则一"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert len(session.calls) == 1
    assert session.calls[0][0] == "http://ollama/api/embed"
    assert session.calls[0][1]["input"] == ["事实一", "规则一"]
    assert session.calls[0][1]["truncate"] is False


def test_ollama_embedding_service_rejects_empty_text():
    with pytest.raises(ValueError, match="non-empty"):
        OllamaBatchEmbeddingService(
            OllamaEmbeddingSettings("http://ollama", "nomic"),
            session=_FakeSession({"embeddings": []}),
        ).embed_batch([""])


def test_ollama_embedding_settings_load_from_environment():
    with patch.dict(
        "os.environ",
        {
            "OLLAMA_BASE_URL": "http://example:11434/",
            "EMBEDDING_MODEL": "embed-model",
            "EMBEDDING_TIMEOUT": "15",
        },
    ):
        settings = OllamaEmbeddingSettings.from_env()

    assert settings.base_url == "http://example:11434"
    assert settings.model == "embed-model"
    assert settings.timeout_seconds == 15
