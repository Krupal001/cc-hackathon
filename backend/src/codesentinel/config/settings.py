"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/codesentinel"

    # GitHub App
    github_app_id: str = ""
    github_webhook_secret: str = ""
    github_private_key: str = ""
    github_private_key_file: str = ""

    # LLM Provider
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    litellm_base_url: str = ""
    litellm_api_key: str = ""

    # Reasoning model config (GPT-5.6 family)
    reasoning_effort: str = "low"

    # Cross-model verifier
    verifier_provider: str = "openai"
    verifier_model: str = "gpt-4o"
    verifier_reasoning_effort: str = "medium"

    # Server
    port: int = 8000
    dashboard_base_url: str = "http://localhost:3000"

    # Review worker
    review_concurrency: int = 3
    review_poll_interval_seconds: int = 2
    review_lock_seconds: int = 900
    review_max_attempts: int = 5
    review_backoff_base_seconds: int = 60

    # Agent configuration
    agent_concurrency: int = 3
    max_files: int = 500
    max_context_kb: int = 256
    max_file_request_rounds: int = 3
    max_tokens_per_agent: int = 4096
    confidence_floor: int = 75
    max_findings: int = 25

    # RAG
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Analytics
    insights_rollup_interval_minutes: int = 60

    @property
    def github_private_key_resolved(self) -> str:
        """Resolve private key from inline env or file path."""
        if self.github_private_key:
            return self.github_private_key.replace("\\n", "\n")
        if self.github_private_key_file:
            path = Path(self.github_private_key_file)
            if path.exists():
                return path.read_text()
        raise ValueError(
            "Either GITHUB_PRIVATE_KEY or GITHUB_PRIVATE_KEY_FILE must be set"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
