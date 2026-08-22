"""Webhook router — receives GitHub webhook events."""

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from structlog import get_logger

from codesentinel.github.webhook import handle_webhook_event, verify_signature

router = APIRouter()
logger = get_logger()


@router.post("/webhook")
async def webhook(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_github_delivery: str = Header(..., alias="X-GitHub-Delivery"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> dict[str, Any]:
    """Receive and dispatch GitHub webhook events."""
    body = await request.body()

    verify_signature(body, x_hub_signature_256)

    payload = json.loads(body)
    action = payload.get("action", "")

    logger.info(
        "webhook_received",
        event=x_github_event,
        action=action,
        delivery=x_github_delivery,
    )

    result = await handle_webhook_event(x_github_event, action, payload)
    return result
