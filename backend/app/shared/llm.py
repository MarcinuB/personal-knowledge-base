from langchain_core.language_models import BaseChatModel

from app.shared.config import Settings


def get_llm(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key)
    elif settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=settings.llm_model, base_url=settings.ollama_base_url)
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider!r}")
