import pytest
from unittest.mock import MagicMock, patch

from app.shared.config import Settings


def _settings(**kwargs) -> Settings:
    defaults = dict(
        llm_provider="ollama",
        embedding_provider="ollama",
        openai_api_key="",
    )
    return Settings(**{**defaults, **kwargs})


@pytest.mark.unit
class TestGetEmbeddings:
    def test_returns_ollama_embeddings(self):
        from app.shared.embeddings import get_embeddings

        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"langchain_ollama": MagicMock(OllamaEmbeddings=mock_cls)}):
            result = get_embeddings(_settings(embedding_provider="ollama"))

        assert result is mock_cls.return_value

    def test_ollama_uses_correct_params(self):
        from app.shared.embeddings import get_embeddings

        mock_cls = MagicMock()
        s = _settings(embedding_provider="ollama", embedding_model="nomic-embed-text", ollama_base_url="http://ollama:11434")
        with patch.dict("sys.modules", {"langchain_ollama": MagicMock(OllamaEmbeddings=mock_cls)}):
            get_embeddings(s)

        mock_cls.assert_called_once_with(model="nomic-embed-text", base_url="http://ollama:11434")

    def test_returns_openai_embeddings(self):
        from app.shared.embeddings import get_embeddings

        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"langchain_openai": MagicMock(OpenAIEmbeddings=mock_cls)}):
            result = get_embeddings(_settings(embedding_provider="openai", openai_api_key="sk-test"))

        assert result is mock_cls.return_value

    def test_openai_uses_correct_params(self):
        from app.shared.embeddings import get_embeddings

        mock_cls = MagicMock()
        s = _settings(embedding_provider="openai", embedding_model="text-embedding-3-small", openai_api_key="sk-test")
        with patch.dict("sys.modules", {"langchain_openai": MagicMock(OpenAIEmbeddings=mock_cls)}):
            get_embeddings(s)

        mock_cls.assert_called_once_with(model="text-embedding-3-small", api_key="sk-test")

    def test_raises_for_unknown_provider(self):
        from app.shared.embeddings import get_embeddings

        s = _settings()
        s.__dict__["embedding_provider"] = "unknown"
        with pytest.raises(ValueError, match="unknown"):
            get_embeddings(s)
