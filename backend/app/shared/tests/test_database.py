import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.unit
class TestSessionFactory:
    def test_session_factory_is_singleton(self):
        from app.shared.database import _get_session_factory, _get_engine

        _get_session_factory.cache_clear()
        _get_engine.cache_clear()

        with patch("app.shared.database.create_async_engine", return_value=MagicMock()):
            f1 = _get_session_factory()
            f2 = _get_session_factory()
            assert f1 is f2

        _get_session_factory.cache_clear()
        _get_engine.cache_clear()

    def test_engine_is_singleton(self):
        from app.shared.database import _get_engine

        _get_engine.cache_clear()

        with patch("app.shared.database.create_async_engine", return_value=MagicMock()) as mock_create:
            _get_engine()
            _get_engine()
            assert mock_create.call_count == 1

        _get_engine.cache_clear()


@pytest.mark.unit
class TestGetDb:
    async def test_get_db_yields_async_session(self):
        from app.shared.database import get_db

        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.shared.database._get_session_factory", return_value=mock_factory):
            gen = get_db()
            session = await gen.__anext__()
            assert session is mock_session


@pytest.mark.integration
class TestDatabaseIntegration:
    @pytest.fixture(autouse=True)
    def postgres_container(self, monkeypatch):
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:16-alpine") as pg:
            url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            monkeypatch.setenv("POSTGRES_URL", url)
            from app.shared.database import _get_engine, _get_session_factory
            from app.shared.config import get_settings

            get_settings.cache_clear()
            _get_engine.cache_clear()
            _get_session_factory.cache_clear()

            yield url

            get_settings.cache_clear()
            _get_engine.cache_clear()
            _get_session_factory.cache_clear()

    async def test_get_db_yields_working_session(self):
        from sqlalchemy import text
        from app.shared.database import get_db

        gen = get_db()
        session = await gen.__anext__()
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    def test_alembic_upgrade_head(self, postgres_container):
        import subprocess
        import sys
        import os

        backend_dir = str(__file__).split("/app/")[0]
        env = {**os.environ, "POSTGRES_URL": postgres_container}
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
