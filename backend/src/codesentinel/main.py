"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from structlog import get_logger

from codesentinel.analytics.insights import start_insights_cron
from codesentinel.api.routers import analytics, health, installations, reviews, webhook
from codesentinel.config.settings import get_settings
from codesentinel.database.session import init_db
from codesentinel.queue.worker import start_worker

logger = get_logger()
_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("server_starting", port=_settings.port)

    # Initialize database (graceful — server starts even without DB)
    db_ready = await init_db()

    worker_task = None
    cron_task = None

    if db_ready:
        worker_task = asyncio.create_task(start_worker())
        cron_task = asyncio.create_task(start_insights_cron())
        logger.info("background_tasks_started", tasks=["review_worker", "insights_cron"])
    else:
        logger.warning("skipping_background_tasks", reason="database_unavailable")

    yield

    # Shutdown
    if worker_task:
        worker_task.cancel()
    if cron_task:
        cron_task.cancel()
    logger.info("server_stopped")


app = FastAPI(
    title="CodeSentinel",
    description="AI-powered GitHub PR review tool — Python + LangGraph backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.dashboard_base_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(reviews.router)
app.include_router(installations.router)
app.include_router(analytics.router)


def main() -> None:
    """Entry point for the codesentinel CLI command."""
    uvicorn.run(
        "codesentinel.main:app",
        host="0.0.0.0",
        port=_settings.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
