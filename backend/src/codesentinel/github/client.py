"""GitHub API client — fetches PR data, posts comments, creates check runs."""

import base64
from typing import Any

import httpx
import yaml

from codesentinel.github.auth import GitHubAuthProvider


class GitHubClient:
    """High-level GitHub API operations for review workflow."""

    def __init__(self, auth: GitHubAuthProvider, installation_id: int) -> None:
        self._auth = auth
        self._installation_id = installation_id
        self._token: str | None = None

    async def _headers(self) -> dict[str, str]:
        if self._token is None:
            self._token = await self._auth.get_installation_token(
                self._installation_id
            )
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(
        self, method: str, url: str, **kwargs
    ) -> httpx.Response:
        headers = await self._headers()
        headers.update(kwargs.pop("headers", {}))
        async with httpx.AsyncClient() as client:
            resp = await client.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp

    async def get_pr(
        self, owner: str, repo: str, pr_number: int
    ) -> dict[str, Any]:
        resp = await self._request(
            "GET",
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
        )
        return resp.json()

    async def get_pr_diff(
        self, owner: str, repo: str, pr_number: int
    ) -> str:
        headers = await self._headers()
        headers["Accept"] = "application/vnd.github.v3.diff"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.text

    async def get_pr_files(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        resp = await self._request(
            "GET",
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files",
        )
        return resp.json()

    async def get_file_contents(
        self, owner: str, repo: str, path: str, ref: str
    ) -> str:
        resp = await self._request(
            "GET",
            f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}",
        )
        data = resp.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8")
        return data.get("content", "")

    async def create_check_run(
        self, owner: str, repo: str, payload: dict
    ) -> dict:
        resp = await self._request(
            "POST",
            f"https://api.github.com/repos/{owner}/{repo}/check-runs",
            json=payload,
        )
        return resp.json()

    async def update_check_run(
        self, owner: str, repo: str, check_run_id: int, payload: dict
    ) -> dict:
        resp = await self._request(
            "PATCH",
            f"https://api.github.com/repos/{owner}/{repo}/check-runs/{check_run_id}",
            json=payload,
        )
        return resp.json()

    async def create_pr_comment(
        self, owner: str, repo: str, pr_number: int, body: str
    ) -> dict:
        resp = await self._request(
            "POST",
            f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )
        return resp.json()

    async def update_pr_comment(
        self, owner: str, repo: str, comment_id: int, body: str
    ) -> dict:
        resp = await self._request(
            "PATCH",
            f"https://api.github.com/repos/{owner}/{repo}/issues/comments/{comment_id}",
            json={"body": body},
        )
        return resp.json()

    async def create_pr_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        event: str,
        body: str,
        comments: list[dict] | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"event": event, "body": body}
        if comments:
            payload["comments"] = comments
        resp = await self._request(
            "POST",
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            json=payload,
        )
        return resp.json()

    async def add_reaction(
        self, owner: str, repo: str, pr_number: int, content: str
    ) -> dict:
        resp = await self._request(
            "POST",
            f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/reactions",
            json={"content": content},
        )
        return resp.json()

    async def delete_reaction(
        self, owner: str, repo: str, reaction_id: int
    ) -> None:
        await self._request(
            "DELETE",
            f"https://api.github.com/repos/{owner}/{repo}/reactions/{reaction_id}",
        )

    async def get_repo_config(
        self, owner: str, repo: str, ref: str, path: str = ".codesentinel.yml"
    ) -> dict | None:
        try:
            content = await self.get_file_contents(owner, repo, path, ref)
            return yaml.safe_load(content)
        except Exception:
            return None

    async def get_conventions(
        self, owner: str, repo: str, ref: str
    ) -> str | None:
        for path in ["AGENTS.md", "CONVENTIONS.md", ".codesentinel/conventions.md"]:
            try:
                return await self.get_file_contents(owner, repo, path, ref)
            except Exception:
                continue
        return None
