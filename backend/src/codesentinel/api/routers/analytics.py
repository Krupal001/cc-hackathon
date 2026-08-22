"""Analytics API router."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from codesentinel.api.deps import get_github_user_id
from codesentinel.database.models import InstallationFPInsight, FindingDisposition, Installation
from codesentinel.database.session import get_db

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


async def _verify_installation_ownership(
    db: AsyncSession, installation_id: int, github_user_id: int | None
) -> None:
    """Verify that the installation belongs to the authenticated user."""
    if github_user_id is None:
        return
    result = await db.execute(
        select(Installation).where(
            Installation.installation_id == installation_id,
            Installation.github_user_id == github_user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied to this installation")


@router.get("/{installation_id}/insights")
async def get_insights(
    installation_id: int,
    db: AsyncSession = Depends(get_db),
    github_user_id: int | None = Depends(get_github_user_id),
) -> dict[str, Any]:
    """Get FP insights for an installation."""
    await _verify_installation_ownership(db, installation_id, github_user_id)
    result = await db.execute(
        select(InstallationFPInsight)
        .where(InstallationFPInsight.installation_id == installation_id)
        .order_by(desc(InstallationFPInsight.computed_at))
    )
    insights = result.scalars().all()
    return {
        "insights": [
            {
                "window": i.window,
                "total_findings": i.total_findings,
                "disputed_findings": i.disputed_findings,
                "resolved_findings": i.resolved_findings,
                "quiet_drops": i.quiet_drops,
                "category_dispute_rates": i.category_dispute_rates,
                "computed_at": i.computed_at.isoformat() if i.computed_at else None,
            }
            for i in insights
        ]
    }


@router.get("/{installation_id}/dispositions")
async def get_dispositions(
    installation_id: int,
    repo: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    github_user_id: int | None = Depends(get_github_user_id),
) -> dict[str, Any]:
    """Get finding dispositions for an installation."""
    await _verify_installation_ownership(db, installation_id, github_user_id)
    query = (
        select(FindingDisposition)
        .where(FindingDisposition.installation_id == installation_id)
        .order_by(desc(FindingDisposition.last_seen_at))
        .limit(limit)
    )
    if repo:
        query = query.where(FindingDisposition.repo_full_name == repo)

    result = await db.execute(query)
    dispositions = result.scalars().all()
    return {
        "dispositions": [
            {
                "repo_full_name": d.repo_full_name,
                "finding_match_key": d.finding_match_key,
                "category": d.category,
                "severity": d.severity,
                "surface_count": d.surface_count,
                "dispute_count": d.dispute_count,
                "resolve_count": d.resolve_count,
                "verified_count": d.verified_count,
                "silent_drop_count": d.silent_drop_count,
                "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
            }
            for d in dispositions
        ]
    }
