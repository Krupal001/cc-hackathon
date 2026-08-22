"""Review processor — executes review jobs and posts results to GitHub."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from sqlalchemy import select, update
from structlog import get_logger

from codesentinel.agents.pipeline import run_review
from codesentinel.config.settings import get_settings
from codesentinel.database.models import Review, ReviewJob
from codesentinel.database.session import async_session_factory
from codesentinel.github.auth import get_github_auth
from codesentinel.github.client import GitHubClient

logger = get_logger()
_settings = get_settings()

BOT_COMMENT_MARKER = "<!-- codesentinel-review -->"


def _format_review_comment(
    summary: str,
    findings: list[dict],
    diagram: str,
    merge_score: int,
    merge_score_reason: str,
    delta_caption: str,
    cost_usd: float,
) -> str:
    """Format the GitHub review comment as markdown."""
    parts = [BOT_COMMENT_MARKER]

    score_emoji = {1: "🚫", 2: "⚠️", 3: "⚡", 4: "✅", 5: "🎉"}
    emoji = score_emoji.get(merge_score, "📝")

    parts.append(f"## {emoji} Code Review — {merge_score}/5")
    parts.append(f"*{merge_score_reason}*\n")

    if delta_caption:
        parts.append(f"> 📋 **Delta:** {delta_caption}\n")

    parts.append(f"### Summary\n\n{summary}\n")

    if findings:
        parts.append("### Findings\n")
        parts.append(
            "| Severity | File | Line | Finding | Confidence | Status |"
        )
        parts.append("|----------|------|------|---------|------------|--------|")
        for f in findings:
            sev_emoji = {
                "critical": "🔴",
                "warning": "🟡",
                "info": "🔵",
            }.get(f.get("severity", "info"), "⚪")
            verification = f.get("verification", "")
            status = ""
            if verification == "verified":
                status = "✅"
            elif verification == "unverified":
                status = "❓"
            parts.append(
                f"| {sev_emoji} {f['severity']} | `{f['file']}` | {f['line']} "
                f"| {f['title']} | {f.get('confidence', 100)}% | {status} |"
            )
        parts.append("")

        parts.append("### Details\n")
        for f in findings:
            parts.append(f"#### {f['title']}")
            parts.append(f"- **File:** `{f['file']}:{f['line']}`")
            parts.append(f"- **Severity:** {f['severity']}")
            parts.append(f"- **Category:** {f.get('category', 'general')}")
            parts.append(f"- **Confidence:** {f.get('confidence', 100)}%")
            if f.get("verification"):
                parts.append(f"- **Verification:** {f['verification']}")
            parts.append(f"\n{f['description']}\n")
            parts.append(f"**Suggestion:** {f['suggestion']}\n")
    else:
        parts.append("### ✅ No issues found. Clean review!\n")

    if diagram and diagram.startswith("flowchart"):
        parts.append("### Architecture Impact\n")
        parts.append(f"```mermaid\n{diagram}\n```\n")

    if cost_usd > 0:
        parts.append(f"<sub>Estimated cost: ${cost_usd:.4f}</sub>\n")

    return "\n".join(parts)


def _build_inline_comments(findings: list[dict]) -> list[dict]:
    """Build inline comment payloads for GitHub Review API."""
    comments = []
    for f in findings:
        if f.get("severity") in ("critical", "warning"):
            sev_emoji = {"critical": "🔴", "warning": "🟡"}.get(f["severity"], "⚪")
            body = (
                f"{sev_emoji} **{f['title']}**\n\n"
                f"{f['description']}\n\n"
                f"**Suggestion:** {f['suggestion']}"
            )
            comments.append({
                "path": f["file"],
                "line": f["line"],
                "side": "RIGHT",
                "body": body,
            })
    return comments


async def process_review_job(job: ReviewJob) -> None:
    """Execute a single review job end-to-end."""
    payload = job.payload
    installation_id = payload["installation_id"]
    repo_full_name = payload["repo_full_name"]
    pr_number = payload["pr_number"]
    commit_sha = payload["commit_sha"]
    review_mode = payload.get("review_mode", "review")

    owner, repo = repo_full_name.split("/")

    auth = get_github_auth()
    gc = GitHubClient(auth, installation_id)

    pr_number_commit_sha = f"{pr_number}#{commit_sha}"

    logger.info(
        "processing_review",
        repo=repo_full_name,
        pr=pr_number,
        sha=commit_sha[:8],
        mode=review_mode,
    )

    try:
        # Run the LangGraph review pipeline
        result = await run_review(
            github_client=gc,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            commit_sha=commit_sha,
            pr_title=payload.get("pr_title", ""),
            pr_body=payload.get("pr_body", ""),
            review_mode=review_mode,
        )

        findings = result.get("final_findings", [])
        summary = result.get("summary", "")
        diagram = result.get("diagram", "")
        merge_score = result.get("merge_score", 5)
        merge_score_reason = result.get("merge_score_reason", "")
        delta_caption = result.get("delta_caption", "")
        cost = result.get("cost_usd", 0.0)

        # Format and post review comment
        comment_body = _format_review_comment(
            summary=summary,
            findings=findings,
            diagram=diagram,
            merge_score=merge_score,
            merge_score_reason=merge_score_reason,
            delta_caption=delta_caption,
            cost_usd=cost,
        )

        # Check for existing bot comment
        existing_comment_id = await _find_existing_bot_comment(
            gc, owner, repo, pr_number
        )

        if existing_comment_id:
            await gc.update_pr_comment(owner, repo, existing_comment_id, comment_body)
        else:
            comment = await gc.create_pr_comment(owner, repo, pr_number, comment_body)
            comment_id = comment.get("id")

            # Store comment_id
            async with async_session_factory() as session:
                await session.execute(
                    update(Review)
                    .where(
                        Review.repo_full_name == repo_full_name,
                        Review.pr_number_commit_sha == pr_number_commit_sha,
                    )
                    .values(comment_id=comment_id)
                )
                await session.commit()

        # Post inline comments via Review API
        inline_comments = _build_inline_comments(findings)
        if inline_comments:
            event = "COMMENT"
            if merge_score <= 2:
                event = "REQUEST_CHANGES"
            elif merge_score >= 4:
                event = "APPROVE"
            await gc.create_pr_review(
                owner, repo, pr_number, event, summary, inline_comments
            )

        # Create/update check run
        conclusion = "success" if merge_score >= 3 else "failure"
        check_title = f"{merge_score}/5 — {_check_title(findings)}"

        review_detail_url = None
        if _settings.dashboard_base_url:
            encoded = quote(f"{repo_full_name}:{pr_number_commit_sha}")
            review_detail_url = (
                f"{_settings.dashboard_base_url}/dashboard/reviews/{encoded}"
            )

        await gc.create_check_run(
            owner,
            repo,
            {
                "name": "CodeSentinel Review",
                "head_sha": commit_sha,
                "status": "completed",
                "conclusion": conclusion,
                "details_url": review_detail_url,
                "output": {
                    "title": check_title,
                    "summary": merge_score_reason,
                },
            },
        )

        # Store results in database
        await _store_review_result(
            installation_id=installation_id,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            commit_sha=commit_sha,
            pr_number_commit_sha=pr_number_commit_sha,
            status="complete",
            findings=findings,
            summary=summary,
            diagram=diagram,
            merge_score=merge_score,
            merge_score_reason=merge_score_reason,
            tokens=result.get("tokens_used", {}),
            cost=cost,
            enabled_agent_count=result.get("enabled_agent_count", 0),
            review_mode=review_mode,
        )

        logger.info(
            "review_complete",
            repo=repo_full_name,
            pr=pr_number,
            score=merge_score,
            findings=len(findings),
        )

    except Exception as e:
        logger.error(
            "review_failed",
            repo=repo_full_name,
            pr=pr_number,
            error=str(e),
            exc_info=True,
        )

        await _store_review_result(
            installation_id=installation_id,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            commit_sha=commit_sha,
            pr_number_commit_sha=pr_number_commit_sha,
            status="failed",
            findings=[],
            summary="",
            diagram="",
            merge_score=None,
            merge_score_reason="",
            tokens={},
            cost=0.0,
            enabled_agent_count=0,
            review_mode=review_mode,
            error_message=str(e),
        )

        # Create failed check run
        try:
            await gc.create_check_run(
                owner,
                repo,
                {
                    "name": "CodeSentinel Review",
                    "head_sha": commit_sha,
                    "status": "completed",
                    "conclusion": "failure",
                    "output": {
                        "title": "Review failed",
                        "summary": str(e)[:200],
                    },
                },
            )
        except Exception:
            pass

        raise


def _check_title(findings: list[dict]) -> str:
    criticals = sum(1 for f in findings if f.get("severity") == "critical")
    warnings = sum(1 for f in findings if f.get("severity") == "warning")
    infos = sum(1 for f in findings if f.get("severity") == "info")
    parts = []
    if criticals:
        parts.append(f"{criticals} critical")
    if warnings:
        parts.append(f"{warnings} warnings")
    if infos:
        parts.append(f"{infos} info")
    return ", ".join(parts) if parts else "Clean"


async def _find_existing_bot_comment(
    gc: GitHubClient, owner: str, repo: str, pr_number: int
) -> int | None:
    """Find existing bot review comment to update."""
    try:
        import httpx

        token = await gc._auth.get_installation_token(gc._installation_id)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                params={"per_page": 100},
            )
            resp.raise_for_status()
            comments = resp.json()

        for comment in comments:
            if BOT_COMMENT_MARKER in comment.get("body", ""):
                return comment["id"]
    except Exception:
        pass
    return None


async def _store_review_result(
    installation_id: int,
    repo_full_name: str,
    pr_number: int,
    commit_sha: str,
    pr_number_commit_sha: str,
    status: str,
    findings: list,
    summary: str,
    diagram: str,
    merge_score: int | None,
    merge_score_reason: str,
    tokens: dict,
    cost: float,
    enabled_agent_count: int,
    review_mode: str,
    error_message: str | None = None,
) -> None:
    """Store or update review results in the database."""
    async with async_session_factory() as session:
        existing = await session.execute(
            select(Review).where(
                Review.repo_full_name == repo_full_name,
                Review.pr_number_commit_sha == pr_number_commit_sha,
            )
        )
        review = existing.scalar_one_or_none()

        if review:
            review.status = status
            review.findings = findings
            review.summary = summary
            review.diagram = diagram
            review.merge_score = merge_score
            review.merge_score_reason = merge_score_reason
            review.input_tokens = tokens.get("input", 0)
            review.output_tokens = tokens.get("output", 0)
            review.estimated_cost_usd = cost
            review.enabled_agent_count = enabled_agent_count
            review.review_mode = review_mode
            review.error_message = error_message
            review.updated_at = datetime.now(timezone.utc)
        else:
            review = Review(
                installation_id=installation_id,
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                pr_number_commit_sha=pr_number_commit_sha,
                commit_sha=commit_sha,
                status=status,
                findings=findings,
                summary=summary,
                diagram=diagram,
                merge_score=merge_score,
                merge_score_reason=merge_score_reason,
                input_tokens=tokens.get("input", 0),
                output_tokens=tokens.get("output", 0),
                estimated_cost_usd=cost,
                enabled_agent_count=enabled_agent_count,
                review_mode=review_mode,
                error_message=error_message,
            )
            session.add(review)

        await session.commit()
