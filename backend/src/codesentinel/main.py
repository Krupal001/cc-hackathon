"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from structlog import get_logger

from codesentinel.analytics.insights import start_insights_cron
from codesentinel.api.routers import analytics, health, installations, reviews, webhook
from codesentinel.config.settings import get_settings
from codesentinel.database.session import init_db
from codesentinel.queue.worker import start_worker

def _configure_logging() -> None:
    """Configure structlog to emit timestamps in the configured timezone."""
    tz = ZoneInfo(os.environ.get("LOG_TIMEZONE", "Asia/Kolkata"))

    def _timestamper(_logger: object, _method: str, event_dict: dict) -> dict:
        event_dict["timestamp"] = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
        return event_dict

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            _timestamper,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


_configure_logging()
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
    allow_origins=["*"],
    allow_credentials=False,
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
