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
class TestGetLlm:
    def test_returns_ollama_client(self):
        from app.shared.llm import get_llm

        mock_cls = MagicMock()
        with patch("app.shared.llm.ChatOllama", mock_cls, create=True):
            with patch.dict("sys.modules", {"langchain_ollama": MagicMock(ChatOllama=mock_cls)}):
                result = get_llm(_settings(llm_provider="ollama"))

        assert result is mock_cls.return_value

    def test_ollama_uses_correct_params(self):
        from app.shared.llm import get_llm

        mock_cls = MagicMock()
        s = _settings(llm_provider="ollama", ollama_model="llama3", ollama_base_url="http://ollama:11434")
        with patch.dict("sys.modules", {"langchain_ollama": MagicMock(ChatOllama=mock_cls)}):
            get_llm(s)

        mock_cls.assert_called_once_with(model="llama3", base_url="http://ollama:11434")

    def test_returns_openai_client(self):
        from app.shared.llm import get_llm

        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"langchain_openai": MagicMock(ChatOpenAI=mock_cls)}):
            result = get_llm(_settings(llm_provider="openai", openai_api_key="sk-test"))

        assert result is mock_cls.return_value

    def test_openai_uses_correct_params(self):
        from app.shared.llm import get_llm

        mock_cls = MagicMock()
        s = _settings(llm_provider="openai", ollama_model="gpt-4o", openai_api_key="sk-test")
        with patch.dict("sys.modules", {"langchain_openai": MagicMock(ChatOpenAI=mock_cls)}):
            get_llm(s)

        mock_cls.assert_called_once_with(model="gpt-4o", api_key="sk-test")

    def test_raises_for_unknown_provider(self):
        from app.shared.llm import get_llm

        s = _settings()
        s.__dict__["llm_provider"] = "unknown"
        with pytest.raises(ValueError, match="unknown"):
            get_llm(s)
