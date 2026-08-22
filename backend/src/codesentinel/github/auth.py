"""GitHub App authentication using PyGithub + PyJWT."""

import time
from typing import Optional

import httpx
from github import Github
from github.Auth import AppAuth

from codesentinel.config.settings import get_settings


class GitHubAuthProvider:
    """Manages GitHub App authentication and installation tokens."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._app_auth = AppAuth(
            app_id=self._settings.github_app_id,
            private_key=self._settings.github_private_key_resolved,
        )
        self._installation_tokens: dict[int, tuple[str, float]] = {}

    async def get_app_token(self) -> str:
        """Get a JWT for the GitHub App itself."""
        return self._app_auth.token

    async def get_installation_token(self, installation_id: int) -> str:
        """Get an installation access token, with caching."""
        cached = self._installation_tokens.get(installation_id)
        if cached and cached[1] > time.time() + 60:
            return cached[0]

        jwt_token = await self.get_app_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        token = data["token"]
        expires_at = time.time() + 3300
        self._installation_tokens[installation_id] = (token, expires_at)
        return token

    async def get_github(self, installation_id: int) -> Github:
        """Get an authenticated PyGithub instance for an installation."""
        token = await self.get_installation_token(installation_id)
        return Github(login_or_token=token)

    async def get_installation_id_for_repo(
        self, repo_full_name: str
    ) -> Optional[int]:
        """Look up the installation ID for a given repo."""
        jwt_token = await self.get_app_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo_full_name}/installation",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()["id"]


_github_auth: Optional[GitHubAuthProvider] = None


def get_github_auth() -> GitHubAuthProvider:
    global _github_auth
    if _github_auth is None:
        _github_auth = GitHubAuthProvider()
    return _github_auth
