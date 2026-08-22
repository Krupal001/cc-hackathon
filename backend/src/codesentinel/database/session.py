"""Async database session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codesentinel.config.settings import get_settings

_settings = get_settings()

# Normalize Railway/Heroku-style postgres:// or postgresql:// URLs
# to use asyncpg driver for async SQLAlchemy
_db_url = _settings.database_url
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    _db_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> bool:
    """Create all tables and enable required extensions.

    Returns True if successful, False if database is not available.
    For production, use Alembic migrations instead:
        alembic init alembic
        alembic revision --autogenerate -m "initial"
        alembic upgrade head
    """
    from codesentinel.database.models import Base
    from sqlalchemy import text
    from structlog import get_logger

    logger = get_logger()

    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_initialized")
        return True
    except Exception as e:
        logger.warning("database_unavailable", error=str(e))
        return False
