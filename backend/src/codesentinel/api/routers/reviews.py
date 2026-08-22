"""Reviews API router — dashboard data endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from codesentinel.api.deps import get_github_user_id
from codesentinel.database.models import Review, Installation
from codesentinel.database.session import get_db

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("")
async def list_reviews(
    repo: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    github_user_id: int | None = Depends(get_github_user_id),
) -> dict[str, Any]:
    """List reviews with optional filters, scoped to the authenticated user."""
    from sqlalchemy import or_
    query = (
        select(Review)
        .join(Installation, Review.installation_id == Installation.installation_id)
        .order_by(desc(Review.created_at))
        .limit(limit)
        .offset(offset)
    )

    if github_user_id is not None:
        query = query.where(
            or_(
                Installation.github_user_id == github_user_id,
                Installation.github_user_id.is_(None),
            )
        )
    if repo:
        query = query.where(Review.repo_full_name == repo)
    if status:
        query = query.where(Review.status == status)

    result = await db.execute(query)
    reviews = result.scalars().all()

    count_query = (
        select(func.count(Review.id))
        .join(Installation, Review.installation_id == Installation.installation_id)
    )
    if github_user_id is not None:
        count_query = count_query.where(
            or_(
                Installation.github_user_id == github_user_id,
                Installation.github_user_id.is_(None),
            )
        )
    if repo:
        count_query = count_query.where(Review.repo_full_name == repo)
    if status:
        count_query = count_query.where(Review.status == status)
    total = (await db.execute(count_query)).scalar() or 0

    return {
        "reviews": [_serialize_review(r) for r in reviews],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{review_id}")
async def get_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a single review by ID."""
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return _serialize_review(review)


@router.get("/by-key/{repo_full_name}/{pr_number}/{commit_sha}")
async def get_review_by_key(
    repo_full_name: str,
    pr_number: int,
    commit_sha: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get review by repo + PR + commit SHA."""
    pr_number_commit_sha = f"{pr_number}#{commit_sha}"
    result = await db.execute(
        select(Review).where(
            Review.repo_full_name == repo_full_name,
            Review.pr_number_commit_sha == pr_number_commit_sha,
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return _serialize_review(review)


def _serialize_review(r: Review) -> dict[str, Any]:
    return {
        "id": r.id,
        "installation_id": r.installation_id,
        "repo_full_name": r.repo_full_name,
        "pr_number": r.pr_number,
        "commit_sha": r.commit_sha,
        "status": r.status,
        "findings": r.findings,
        "summary": r.summary,
        "diagram": r.diagram,
        "merge_score": r.merge_score,
        "merge_score_reason": r.merge_score_reason,
        "input_tokens": r.input_tokens,
        "output_tokens": r.output_tokens,
        "estimated_cost_usd": r.estimated_cost_usd,
        "enabled_agent_count": r.enabled_agent_count,
        "review_mode": r.review_mode,
        "error_message": r.error_message,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }
