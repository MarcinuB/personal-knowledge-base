import asyncio
import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    alembic_cfg = Config("alembic.ini")
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    yield


app = FastAPI(
    title="Personal Knowledge Base API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.knowledge.router import router as knowledge_router
from app.chat.router import router as chat_router, chat_router as chat_endpoint_router
from app.connectors.router import router as connectors_router
app.include_router(knowledge_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(chat_endpoint_router, prefix="/api")
app.include_router(connectors_router, prefix="/api")

import uuid as _uuid
from app.shared.config import get_settings as _get_settings
from app.connectors.dummy import DummyConnector as _DummyConnector
from app.connectors.base import ConnectorConfig as _ConnectorConfig
from app.connectors.service import connector_service as _connector_service

_settings = _get_settings()
if _settings.dummy_collection_id:
    _connector_service.register(_DummyConnector(_ConnectorConfig(
        name="dummy",
        source_type="dummy",
        collection_id=_uuid.UUID(_settings.dummy_collection_id),
    )))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
