"""Webhook signature verification and event dispatch."""

import hashlib
import hmac
from typing import Any

from fastapi import HTTPException
from structlog import get_logger

from codesentinel.config.settings import get_settings
from codesentinel.database.session import async_session_factory
from codesentinel.database.models import ReviewJob, Installation
from codesentinel.github.auth import get_github_auth
from codesentinel.github.client import GitHubClient

logger = get_logger()
_settings = get_settings()

REVIEW_TRIGGERING_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


def verify_signature(payload_body: bytes, signature_header: str | None) -> None:
    if not signature_header:
        raise HTTPException(
            status_code=403, detail="Missing X-Hub-Signature-256 header"
        )

    expected = "sha256=" + hmac.new(
        _settings.github_webhook_secret.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=403, detail="Invalid signature")


async def handle_webhook_event(
    event: str,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Route webhook events to appropriate handlers."""

    if event == "pull_request" and action in REVIEW_TRIGGERING_ACTIONS:
        return await _handle_pull_request(payload)
    elif event == "issue_comment":
        return await _handle_issue_comment(payload)
    elif event == "pull_request_review_comment":
        return await _handle_review_comment(payload)
    elif event == "installation":
        return await _handle_installation(payload, action)
    elif event == "installation_repositories":
        return await _handle_installation_repositories(payload, action)
    elif event == "check_run" and action == "rerequested":
        return await _handle_check_rerequest(payload)
    else:
        return {"status": "ignored", "event": event, "action": action}


async def _handle_pull_request(payload: dict) -> dict:
    pr = payload["pull_request"]
    repo = payload["repository"]
    installation = payload["installation"]

    repo_full_name = repo["full_name"]
    pr_number = pr["number"]
    commit_sha = pr["head"]["sha"]

    if pr.get("draft") and not _should_review_draft(pr):
        return {"status": "skipped", "reason": "draft_pr"}

    if _is_bot_actor(pr.get("user", {})):
        return {"status": "skipped", "reason": "bot_author"}

    job_payload = {
        "installation_id": installation["id"],
        "repo_full_name": repo_full_name,
        "pr_number": pr_number,
        "commit_sha": commit_sha,
        "pr_title": pr.get("title", ""),
        "pr_body": pr.get("body", ""),
        "pr_head_ref": pr.get("head", {}).get("ref", ""),
        "pr_base_ref": pr.get("base", {}).get("ref", ""),
        "review_mode": "review",
        "author": pr.get("user", {}).get("login", ""),
        "is_draft": pr.get("draft", False),
    }

    await _enqueue_review(job_payload)
    logger.info(
        "review_enqueued", repo=repo_full_name, pr=pr_number, sha=commit_sha[:8]
    )
    return {"status": "enqueued", "pr_number": pr_number}


async def _handle_issue_comment(payload: dict) -> dict:
    comment = payload["comment"]
    issue = payload["issue"]
    repo = payload["repository"]
    installation = payload["installation"]

    body = comment.get("body", "")
    if "@codesentinel" not in body.lower():
        return {"status": "ignored", "reason": "no_mention"}

    if not issue.get("pull_request"):
        return {"status": "ignored", "reason": "not_pr"}

    if _is_bot_actor(comment.get("user", {})):
        return {"status": "skipped", "reason": "bot_comment"}

    parts = body.lower().split()
    mode = "review"
    if "summary" in parts:
        mode = "summary"
    elif "respond" in parts or len(parts) > 2:
        mode = "respond"

    pr_number = issue["number"]
    commit_sha = await _get_pr_head_sha(
        installation["id"], repo["full_name"], pr_number
    )

    job_payload = {
        "installation_id": installation["id"],
        "repo_full_name": repo["full_name"],
        "pr_number": pr_number,
        "commit_sha": commit_sha,
        "pr_title": issue.get("title", ""),
        "pr_body": issue.get("body", ""),
        "review_mode": mode,
        "comment_body": body,
        "comment_id": comment.get("id"),
    }

    await _enqueue_review(job_payload)
    return {"status": "enqueued", "mode": mode}


async def _handle_review_comment(payload: dict) -> dict:
    comment = payload["comment"]
    repo = payload["repository"]
    installation = payload["installation"]

    if _is_bot_actor(comment.get("user", {})):
        return {"status": "skipped", "reason": "bot_comment"}

    pr = payload.get("pull_request", {})
    job_payload = {
        "installation_id": installation["id"],
        "repo_full_name": repo["full_name"],
        "pr_number": pr.get("number"),
        "commit_sha": pr.get("head", {}).get("sha", ""),
        "review_mode": "inline_reply",
        "comment_body": comment.get("body", ""),
        "comment_id": comment.get("id"),
        "in_reply_to_id": comment.get("in_reply_to_id"),
        "path": comment.get("path"),
        "line": comment.get("line"),
    }

    await _enqueue_review(job_payload)
    return {"status": "enqueued", "mode": "inline_reply"}


async def _handle_installation(payload: dict, action: str) -> dict:
    installation = payload["installation"]
    installation_id = installation["id"]
    sender = payload.get("sender", {})
    github_user_id = sender.get("id")
    github_user_login = sender.get("login")

    if action == "created":
        repos = payload.get("repositories", [])
        async with async_session_factory() as session:
            from sqlalchemy import select

            for repo in repos:
                existing = await session.execute(
                    select(Installation).where(
                        Installation.installation_id == installation_id,
                        Installation.repo_full_name == repo["full_name"],
                    )
                )
                record = existing.scalar_one_or_none()
                if record:
                    record.github_user_id = github_user_id
                    record.github_user_login = github_user_login
                else:
                    session.add(
                        Installation(
                            installation_id=installation_id,
                            repo_full_name=repo["full_name"],
                            config={},
                            github_user_id=github_user_id,
                            github_user_login=github_user_login,
                        )
                    )
            await session.commit()
        logger.info(
            "installation_created", installation_id=installation_id, repos=len(repos)
        )
        return {"status": "installed", "repos": len(repos)}

    elif action == "deleted":
        async with async_session_factory() as session:
            from sqlalchemy import delete

            await session.execute(
                delete(Installation).where(
                    Installation.installation_id == installation_id
                )
            )
            await session.commit()
        return {"status": "uninstalled"}

    return {"status": "ignored"}


async def _handle_installation_repositories(payload: dict, action: str) -> dict:
    installation = payload["installation"]
    installation_id = installation["id"]

    if action == "added":
        repos = payload.get("repositories_added", [])
        sender = payload.get("sender", {})
        github_user_id = sender.get("id")
        github_user_login = sender.get("login")
        async with async_session_factory() as session:
            from sqlalchemy import select

            for repo in repos:
                existing = await session.execute(
                    select(Installation).where(
                        Installation.installation_id == installation_id,
                        Installation.repo_full_name == repo["full_name"],
                    )
                )
                record = existing.scalar_one_or_none()
                if record:
                    record.github_user_id = github_user_id
                    record.github_user_login = github_user_login
                else:
                    session.add(
                        Installation(
                            installation_id=installation_id,
                            repo_full_name=repo["full_name"],
                            config={},
                            github_user_id=github_user_id,
                            github_user_login=github_user_login,
                        )
                    )
            await session.commit()
        logger.info(
            "repos_added", installation_id=installation_id, repos=len(repos)
        )
        return {"status": "repos_added", "count": len(repos)}

    elif action == "removed":
        repos = payload.get("repositories_removed", [])
        async with async_session_factory() as session:
            from sqlalchemy import delete

            for repo in repos:
                await session.execute(
                    delete(Installation).where(
                        Installation.installation_id == installation_id,
                        Installation.repo_full_name == repo["full_name"],
                    )
                )
            await session.commit()
        return {"status": "repos_removed", "count": len(repos)}

    return {"status": "ignored"}


async def _handle_check_rerequest(payload: dict) -> dict:
    check_run = payload["check_run"]
    repo = payload["repository"]
    installation = payload["installation"]

    pr_refs = check_run.get("check_suite", {}).get("pull_requests", [])
    pr_number = pr_refs[0].get("number") if pr_refs else None
    if not pr_number:
        return {"status": "ignored", "reason": "no_pr"}

    commit_sha = check_run.get("head_sha", "")
    job_payload = {
        "installation_id": installation["id"],
        "repo_full_name": repo["full_name"],
        "pr_number": pr_number,
        "commit_sha": commit_sha,
        "review_mode": "review",
    }

    await _enqueue_review(job_payload)
    return {"status": "enqueued"}


async def _enqueue_review(job_payload: dict) -> None:
    async with async_session_factory() as session:
        job = ReviewJob(
            installation_id=job_payload["installation_id"],
            repo_full_name=job_payload["repo_full_name"],
            pr_number=job_payload["pr_number"],
            commit_sha=job_payload["commit_sha"],
            payload=job_payload,
            status="queued",
        )
        session.add(job)
        await session.commit()


async def _get_pr_head_sha(
    installation_id: int, repo_full_name: str, pr_number: int
) -> str:
    auth = get_github_auth()
    client = GitHubClient(auth, installation_id)
    owner, repo = repo_full_name.split("/")
    pr = await client.get_pr(owner, repo, pr_number)
    return pr["head"]["sha"]


def _is_bot_actor(user: dict) -> bool:
    login = user.get("login", "").lower()
    return (
        login == "code-sentinal[bot]"
        or login == "codesentinel[bot]"
        or login.endswith("[bot]")
    )


def _should_review_draft(pr: dict) -> bool:
    return False
