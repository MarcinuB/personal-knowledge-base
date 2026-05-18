import pytest
from unittest.mock import patch

from app.shared.config import Settings, get_settings


@pytest.mark.unit
class TestSettingsDefaults:
    def test_llm_defaults(self):
        s = Settings()
        assert s.llm_provider == "ollama"
        assert s.ollama_base_url == "http://ollama:11434"
        assert s.llm_model == "llama3"

    def test_embedding_defaults(self):
        s = Settings()
        assert s.embedding_provider == "ollama"
        assert s.embedding_model == "nomic-embed-text"

    def test_postgres_default(self):
        s = Settings()
        assert s.postgres_url == "postgresql+asyncpg://pkb:pkb@postgres:5432/pkb"

    def test_chromadb_defaults(self):
        s = Settings()
        assert s.chromadb_host == "chromadb"
        assert s.chromadb_port == 8001


@pytest.mark.unit
class TestSettingsEnvOverrides:
    def test_llm_provider_override(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        s = Settings()
        assert s.llm_provider == "openai"

    def test_llm_model_override(self, monkeypatch):
        monkeypatch.setenv("LLM_MODEL", "mistral")
        s = Settings()
        assert s.llm_model == "mistral"

    def test_llm_model_legacy_ollama_model_env(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "mistral")
        s = Settings()
        assert s.llm_model == "mistral"

    def test_openai_api_key_override(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        s = Settings()
        assert s.openai_api_key == "sk-test-123"

    def test_embedding_provider_override(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
        s = Settings()
        assert s.embedding_provider == "openai"

    def test_chromadb_port_override(self, monkeypatch):
        monkeypatch.setenv("CHROMADB_PORT", "9999")
        s = Settings()
        assert s.chromadb_port == 9999

    def test_postgres_url_override(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://user:pass@localhost:5432/testdb")
        s = Settings()
        assert "testdb" in s.postgres_url

    def test_invalid_llm_provider_raises(self):
        with pytest.raises(Exception):
            Settings(llm_provider="invalid_provider")  # type: ignore

    def test_invalid_embedding_provider_raises(self):
        with pytest.raises(Exception):
            Settings(embedding_provider="invalid_provider")  # type: ignore


@pytest.mark.unit
class TestGetSettingsSingleton:
    def test_returns_settings_instance(self):
        s = get_settings()
        assert isinstance(s, Settings)

    def test_cached_returns_same_instance(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_cache_can_be_cleared(self):
        get_settings.cache_clear()
        s1 = get_settings()
        get_settings.cache_clear()
        s2 = get_settings()
        # Different instances after cache clear, but both valid
        assert isinstance(s1, Settings)
        assert isinstance(s2, Settings)
