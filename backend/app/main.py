import asyncio
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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

# Domain routers are registered here as phases are completed:
# from app.knowledge.router import router as knowledge_router
# from app.chat.router import router as chat_router
# from app.connectors.router import router as connectors_router
# app.include_router(knowledge_router, prefix="/api/knowledge", tags=["knowledge"])
# app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
# app.include_router(connectors_router, prefix="/api/connectors", tags=["connectors"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
