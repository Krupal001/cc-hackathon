"""Installations API router."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from codesentinel.api.deps import get_github_user_id
from codesentinel.database.models import Installation, InstallationSettings, Review
from codesentinel.database.session import get_db

router = APIRouter(prefix="/api/installations", tags=["installations"])


@router.get("")
async def list_installations(
    db: AsyncSession = Depends(get_db),
    github_user_id: int | None = Depends(get_github_user_id),
) -> dict[str, Any]:
    """List installations, filtered by the authenticated user."""
    query = select(Installation).order_by(desc(Installation.updated_at))
    if github_user_id is not None:
        query = query.where(Installation.github_user_id == github_user_id)
    result = await db.execute(query)
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
) -> dict[str, Any]:
    """List repos for an installation."""
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
) -> dict[str, Any]:
    """Get installation settings."""
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
) -> dict[str, Any]:
    """Update installation settings."""
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
