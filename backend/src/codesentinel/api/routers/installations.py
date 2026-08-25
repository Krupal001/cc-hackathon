"""Installations API router."""

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from codesentinel.api.deps import get_github_user_id, get_github_access_token
from codesentinel.database.models import Installation, InstallationSettings, Review
from codesentinel.database.session import get_db

router = APIRouter(prefix="/api/installations", tags=["installations"])


async def _auto_claim_installations(
    db: AsyncSession,
    github_user_id: int,
    access_token: str,
) -> None:
    """Use GitHub API to find the user's installations and stamp github_user_id on NULL rows."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://api.github.com/user/installations",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            if resp.status_code != 200:
                return
            installation_ids = [i["id"] for i in resp.json().get("installations", [])]
        if not installation_ids:
            return
        await db.execute(
            update(Installation)
            .where(
                Installation.installation_id.in_(installation_ids),
                Installation.github_user_id.is_(None),
            )
            .values(github_user_id=github_user_id)
        )
        await db.commit()
    except Exception:
        pass


async def _require_installation_owner(
    db: AsyncSession,
    installation_id: int,
    github_user_id: int | None,
) -> None:
    """Raise 403 if the installation does not belong to the authenticated user."""
    if github_user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    result = await db.execute(
        select(Installation.id).where(
            Installation.installation_id == installation_id,
            Installation.github_user_id == github_user_id,
        ).limit(1)
    )
    if not result.scalar():
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("")
async def list_installations(
    db: AsyncSession = Depends(get_db),
    github_user_id: int | None = Depends(get_github_user_id),
    access_token: str | None = Depends(get_github_access_token),
) -> dict[str, Any]:
    """List installations for the authenticated user only."""
    if github_user_id is None:
        return {"installations": []}
    if access_token:
        await _auto_claim_installations(db, github_user_id, access_token)
    result = await db.execute(
        select(Installation)
        .where(Installation.github_user_id == github_user_id)
        .order_by(desc(Installation.updated_at))
    )
    installations = result.scalars().all()
    return {
        "installations": [
            {
                "installation_id": i.installation_id,
                "repo_full_name": i.repo_full_name,
                "model_id": i.model_id,
                "config": i.config,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in installations
        ]
    }


@router.get("/{installation_id}/repos")
async def list_repos(
    installation_id: int,
    db: AsyncSession = Depends(get_db),
    github_user_id: int | None = Depends(get_github_user_id),
) -> dict[str, Any]:
    """List repos for an installation, scoped to the authenticated user."""
    await _require_installation_owner(db, installation_id, github_user_id)
    result = await db.execute(
        select(Installation).where(Installation.installation_id == installation_id)
    )
    installations = result.scalars().all()
    return {
        "repos": [
            {
                "repo_full_name": i.repo_full_name,
                "model_id": i.model_id,
                "config": i.config,
            }
            for i in installations
        ]
    }


@router.get("/{installation_id}/settings")
async def get_settings(
    installation_id: int,
    db: AsyncSession = Depends(get_db),
    github_user_id: int | None = Depends(get_github_user_id),
) -> dict[str, Any]:
    """Get installation settings, scoped to the authenticated user."""
    await _require_installation_owner(db, installation_id, github_user_id)
    settings = await db.get(InstallationSettings, installation_id)
    if not settings:
        return {"installation_id": installation_id, "settings": None}
    return {
        "installation_id": installation_id,
        "settings": {
            "min_severity": settings.min_severity,
            "comment_types": settings.comment_types,
            "max_comments": settings.max_comments,
            "post_summary": settings.post_summary,
            "custom_instructions": settings.custom_instructions,
            "comment_header": settings.comment_header,
            "custom_agents": settings.custom_agents,
        },
    }


@router.put("/{installation_id}/settings")
async def update_settings(
    installation_id: int,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    github_user_id: int | None = Depends(get_github_user_id),
) -> dict[str, Any]:
    """Update installation settings, scoped to the authenticated user."""
    await _require_installation_owner(db, installation_id, github_user_id)
    settings = await db.get(InstallationSettings, installation_id)
    if not settings:
        settings = InstallationSettings(installation_id=installation_id)
        db.add(settings)

    for key in [
        "min_severity", "comment_types", "max_comments", "post_summary",
        "custom_instructions", "comment_header", "custom_agents",
    ]:
        if key in body:
            setattr(settings, key, body[key])

    await db.commit()
    return {"status": "updated"}
