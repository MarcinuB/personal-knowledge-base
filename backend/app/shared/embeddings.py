from langchain_core.embeddings import Embeddings

from app.shared.config import Settings


def get_embeddings(settings: Settings) -> Embeddings:
    if settings.embedding_provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)
    elif settings.embedding_provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(model=settings.embedding_model, base_url=settings.ollama_base_url)
    else:
        raise ValueError(f"Unknown embedding provider: {settings.embedding_provider!r}")
