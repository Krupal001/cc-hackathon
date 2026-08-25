"""FastAPI dependencies for user-level data isolation."""

from fastapi import Header, HTTPException


async def get_github_user_id(
    x_github_user_id: str | None = Header(None, alias="X-GitHub-User-Id"),
) -> int | None:
    """Extract the GitHub user ID from the request header.

    Returns None if the header is not present (e.g. webhook calls).
    API endpoints that serve dashboard data should use this to filter
    results to only the authenticated user's installations.
    """
    if x_github_user_id is None:
        return None
    try:
        return int(x_github_user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid X-GitHub-User-Id header")


async def get_github_access_token(
    x_github_access_token: str | None = Header(None, alias="X-GitHub-Access-Token"),
) -> str | None:
    """Extract the GitHub OAuth access token from the request header."""
    return x_github_access_token
