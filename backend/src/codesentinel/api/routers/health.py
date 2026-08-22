"""Health check router."""

from fastapi import APIRouter
from sqlalchemy import text

from codesentinel.config.settings import get_settings
from codesentinel.database.session import engine

router = APIRouter()
_settings = get_settings()


@router.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    db_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "version": "0.1.0",
        "db": "connected" if db_ok else "disconnected",
        "llm_provider": _settings.llm_provider,
        "llm_model": _settings.llm_model,
    }
