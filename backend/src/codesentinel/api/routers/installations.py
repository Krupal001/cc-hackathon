"""Installations API router."""

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from codesentinel.api.deps import get_github_user_id, get_github_access_token
from codesentinel.database.models import Installation, InstallationSettings, Review
from codesentinel.database.session import get_db

router = APIRouter(prefix="/api/installations", tags=["installations"])
logger = get_logger()


async def _auto_claim_installations(
    db: AsyncSession,
    github_user_id: int,
    access_token: str,
) -> list[int]:
    """Use the user's OAuth token to discover their installations.
    Stamps github_user_id on any legacy NULL rows and returns the installation IDs.
    """
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
                return []
            installation_ids = [i["id"] for i in resp.json().get("installations", [])]
        if not installation_ids:
            return []
        await db.execute(
            update(Installation)
            .where(
                Installation.installation_id.in_(installation_ids),
                Installation.github_user_id.is_(None),
            )
            .values(github_user_id=github_user_id)
        )
        await db.commit()
        return installation_ids
    except Exception:
        return []


async def _sync_installation_repos(
    db: AsyncSession,
    installation_id: int,
    github_user_id: int,
) -> None:
    """Fetch the actual repos accessible to an installation from GitHub and reconcile the DB.

    This handles:
    - Repos added or removed after the initial install (without relying solely on webhooks)
    - Installs with 'All repositories' access (webhook payload is empty, API is not)
    - Missed webhook deliveries
    """
    from codesentinel.github.auth import get_github_auth

    try:
        auth = get_github_auth()
        token = await auth.get_installation_token(installation_id)

        current_repos: set[str] = set()
        page = 1
        async with httpx.AsyncClient(timeout=10.0) as client:
            while True:
                resp = await client.get(
                    "https://api.github.com/installation/repositories",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                    },
                    params={"per_page": 100, "page": page},
                )
                if resp.status_code != 200:
                    return
                data = resp.json()
                repos = data.get("repositories", [])
                current_repos.update(r["full_name"] for r in repos)
                if len(repos) < 100:
                    break
                page += 1

        # Repos currently stored in DB for this installation
        result = await db.execute(
            select(Installation.repo_full_name).where(
                Installation.installation_id == installation_id,
            )
        )
        db_repos: set[str] = {row[0] for row in result.fetchall()}

        added = current_repos - db_repos
        removed = db_repos - current_repos

        for repo_name in added:
            db.add(
                Installation(
                    installation_id=installation_id,
                    repo_full_name=repo_name,
                    github_user_id=github_user_id,
                    config={},
                )
            )

        if removed:
            await db.execute(
                delete(Installation).where(
                    Installation.installation_id == installation_id,
                    Installation.repo_full_name.in_(removed),
                )
            )

        if added or removed:
            await db.commit()
            logger.info(
                "installation_repos_synced",
                installation_id=installation_id,
                added=len(added),
                removed=len(removed),
            )

    except Exception as exc:
        logger.warning("installation_repos_sync_failed", installation_id=installation_id, error=str(exc))


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

    # Step 1: Try to claim legacy NULL rows via OAuth token (best-effort)
    if access_token:
        await _auto_claim_installations(db, github_user_id, access_token)

    # Step 2: Get ALL installation IDs we already know about for this user
    id_result = await db.execute(
        select(Installation.installation_id)
        .where(Installation.github_user_id == github_user_id)
        .distinct()
    )
    known_install_ids = [row[0] for row in id_result.fetchall()]

    # Step 3: Sync each installation's repos from GitHub API (source of truth).
    # This runs even if Step 1 failed — ensuring stale repos are cleaned up.
    if known_install_ids:
        logger.info("syncing_installation_repos", installation_ids=known_install_ids)
        await asyncio.gather(
            *[_sync_installation_repos(db, iid, github_user_id) for iid in known_install_ids],
            return_exceptions=True,
        )

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
