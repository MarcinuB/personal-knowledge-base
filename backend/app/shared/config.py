from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM
    llm_provider: Literal["ollama", "openai"] = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3"
    openai_api_key: str = ""

    # Embeddings
    embedding_provider: Literal["ollama", "openai"] = "ollama"
    embedding_model: str = "nomic-embed-text"

    # PostgreSQL
    postgres_url: str = "postgresql+asyncpg://pkb:pkb@postgres:5432/pkb"

    # ChromaDB
    chromadb_host: str = "chromadb"
    chromadb_port: int = 8001

    # Connectors
    dummy_collection_id: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
