import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from langchain_core.documents import Document
from pydantic import BaseModel


class ConnectorConfig(BaseModel):
    name: str
    source_type: str          # "dummy" | "google_drive" | "obsidian"
    collection_id: uuid.UUID  # target collection UUID
    settings: dict = {}       # source-specific config (credentials, paths, etc.)


class BaseConnector(ABC):
    def __init__(self, config: ConnectorConfig) -> None:
        self.config = config

    @abstractmethod
    async def sync(self) -> AsyncIterator[Document]:
        """Yield LangChain Documents one by one."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the source is reachable."""
        ...

    @property
    def name(self) -> str:
        return self.config.name
