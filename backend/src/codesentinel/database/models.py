"""SQLAlchemy database models for Code-Sentinal."""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Installation(Base):
    __tablename__ = "installations"
    __table_args__ = (
        UniqueConstraint("installation_id", "repo_full_name", name="uq_install_repo"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    installation_id = Column(BigInteger, nullable=False, index=True)
    repo_full_name = Column(String(255), nullable=False, index=True)
    config = Column(JSONB, default=dict)
    model_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)



class InstallationSettings(Base):
    __tablename__ = "installation_settings"

    installation_id = Column(BigInteger, primary_key=True)
    min_severity = Column(String(20), default="info")
    comment_types = Column(JSONB, default=list)
    max_comments = Column(Integer, default=25)
    post_summary = Column(String(10), default="always")
    custom_instructions = Column(Text, default="")
    comment_header = Column(String(200), default="")
    custom_agents = Column(JSONB, default=list)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)



class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint(
            "repo_full_name", "pr_number_commit_sha", name="uq_review_pr_commit"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    installation_id = Column(BigInteger, nullable=False, index=True)
    repo_full_name = Column(String(255), nullable=False, index=True)
    pr_number = Column(Integer, nullable=False)
    pr_number_commit_sha = Column(String(300), nullable=False)
    commit_sha = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    findings = Column(JSONB, default=list)
    summary = Column(Text, default="")
    diagram = Column(Text, default="")
    merge_score = Column(Integer, nullable=True)
    merge_score_reason = Column(Text, default="")
    comment_id = Column(BigInteger, nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    enabled_agent_count = Column(Integer, default=0)
    changed_lines = Column(Integer, default=0)
    review_mode = Column(String(20), default="review")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)



class ReviewJob(Base):
    __tablename__ = "review_jobs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    installation_id = Column(BigInteger, nullable=False, index=True)
    repo_full_name = Column(String(255), nullable=False)
    pr_number = Column(Integer, nullable=False)
    commit_sha = Column(String(40), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    attempts = Column(Integer, default=0)
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String(100), nullable=True)
    next_attempt_at = Column(DateTime, default=utcnow)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class FindingDisposition(Base):
    __tablename__ = "finding_dispositions"
    __table_args__ = (
        UniqueConstraint(
            "installation_id",
            "repo_full_name",
            "finding_match_key",
            name="uq_disposition_finding",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    installation_id = Column(BigInteger, nullable=False, index=True)
    repo_full_name = Column(String(255), nullable=False)
    finding_match_key = Column(String(500), nullable=False)
    category = Column(String(100), default="")
    severity = Column(String(20), default="")
    surface_count = Column(Integer, default=0)
    dispute_count = Column(Integer, default=0)
    resolve_count = Column(Integer, default=0)
    verified_count = Column(Integer, default=0)
    silent_drop_count = Column(Integer, default=0)
    agreement_count = Column(Integer, default=0)
    last_seen_at = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)


class InstallationFPInsight(Base):
    __tablename__ = "installation_fp_insights"
    __table_args__ = (
        UniqueConstraint("installation_id", "window", name="uq_fp_insight_window"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    installation_id = Column(BigInteger, nullable=False, index=True)
    window = Column(String(20), nullable=False)
    total_findings = Column(Integer, default=0)
    disputed_findings = Column(Integer, default=0)
    resolved_findings = Column(Integer, default=0)
    quiet_drops = Column(Integer, default=0)
    category_dispute_rates = Column(JSONB, default=dict)
    top_clusters = Column(JSONB, default=list)
    computed_at = Column(DateTime, default=utcnow)


class PRLifecycle(Base):
    __tablename__ = "pr_lifecycle"
    __table_args__ = (
        UniqueConstraint(
            "installation_id",
            "repo_full_name",
            "pr_number",
            name="uq_pr_lifecycle",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    installation_id = Column(BigInteger, nullable=False, index=True)
    repo_full_name = Column(String(255), nullable=False)
    pr_number = Column(Integer, nullable=False)
    opened_at = Column(DateTime, nullable=True)
    first_review_at = Column(DateTime, nullable=True)
    merged_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class HelpfulVote(Base):
    __tablename__ = "helpful_votes"
    __table_args__ = (
        UniqueConstraint(
            "installation_id",
            "repo_full_name",
            "pr_number",
            name="uq_helpful_vote",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    installation_id = Column(BigInteger, nullable=False, index=True)
    repo_full_name = Column(String(255), nullable=False)
    pr_number = Column(Integer, nullable=False)
    vote_type = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=utcnow)


class ReviewCost(Base):
    __tablename__ = "review_costs"
    __table_args__ = (
        UniqueConstraint(
            "installation_id",
            "repo_full_name",
            "pr_number",
            "commit_sha",
            name="uq_review_cost",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    installation_id = Column(BigInteger, nullable=False, index=True)
    repo_full_name = Column(String(255), nullable=False)
    pr_number = Column(Integer, nullable=False)
    commit_sha = Column(String(40), nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    agent_breakdown = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=utcnow)



class CodebaseEmbedding(Base):
    __tablename__ = "codebase_embeddings"
    __table_args__ = (
        Index("ix_embeddings_repo_sha", "repo_full_name", "commit_sha"),
        Index(
            "ix_embeddings_vector",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_full_name = Column(String(255), nullable=False)
    commit_sha = Column(String(40), nullable=False)
    file_path = Column(String(500), nullable=False)
    content_chunk = Column(Text, nullable=False)
    chunk_index = Column(Integer, default=0)
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime, default=utcnow)
