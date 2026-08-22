"""Initial schema — all tables.

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "installations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "installation_id", "repo_full_name", name="uq_install_repo"
        ),
    )
    op.create_index(
        "ix_installations_installation_id", "installations", ["installation_id"]
    )
    op.create_index(
        "ix_installations_repo_full_name", "installations", ["repo_full_name"]
    )

    op.create_table(
        "installation_settings",
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("min_severity", sa.String(20), nullable=True),
        sa.Column("comment_types", postgresql.JSONB(), nullable=True),
        sa.Column("max_comments", sa.Integer(), nullable=True),
        sa.Column("post_summary", sa.String(10), nullable=True),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.Column("comment_header", sa.String(200), nullable=True),
        sa.Column("custom_agents", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("installation_id"),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("pr_number_commit_sha", sa.String(300), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("findings", postgresql.JSONB(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("diagram", sa.Text(), nullable=True),
        sa.Column("merge_score", sa.Integer(), nullable=True),
        sa.Column("merge_score_reason", sa.Text(), nullable=True),
        sa.Column("comment_id", sa.BigInteger(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("enabled_agent_count", sa.Integer(), nullable=True),
        sa.Column("changed_lines", sa.Integer(), nullable=True),
        sa.Column("review_mode", sa.String(20), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repo_full_name", "pr_number_commit_sha", name="uq_review_pr_commit"
        ),
    )
    op.create_index("ix_reviews_installation_id", "reviews", ["installation_id"])
    op.create_index("ix_reviews_repo_full_name", "reviews", ["repo_full_name"])

    op.create_table(
        "review_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by", sa.String(100), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_review_jobs_installation_id", "review_jobs", ["installation_id"]
    )

    op.create_table(
        "finding_dispositions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("finding_match_key", sa.String(500), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("surface_count", sa.Integer(), nullable=True),
        sa.Column("dispute_count", sa.Integer(), nullable=True),
        sa.Column("resolve_count", sa.Integer(), nullable=True),
        sa.Column("verified_count", sa.Integer(), nullable=True),
        sa.Column("silent_drop_count", sa.Integer(), nullable=True),
        sa.Column("agreement_count", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "installation_id",
            "repo_full_name",
            "finding_match_key",
            name="uq_disposition_finding",
        ),
    )
    op.create_index(
        "ix_finding_dispositions_installation_id",
        "finding_dispositions",
        ["installation_id"],
    )

    op.create_table(
        "installation_fp_insights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("window", sa.String(20), nullable=False),
        sa.Column("total_findings", sa.Integer(), nullable=True),
        sa.Column("disputed_findings", sa.Integer(), nullable=True),
        sa.Column("resolved_findings", sa.Integer(), nullable=True),
        sa.Column("quiet_drops", sa.Integer(), nullable=True),
        sa.Column("category_dispute_rates", postgresql.JSONB(), nullable=True),
        sa.Column("top_clusters", postgresql.JSONB(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("installation_id", "window", name="uq_fp_insight_window"),
    )
    op.create_index(
        "ix_installation_fp_insights_installation_id",
        "installation_fp_insights",
        ["installation_id"],
    )

    op.create_table(
        "pr_lifecycle",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("first_review_at", sa.DateTime(), nullable=True),
        sa.Column("merged_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "installation_id",
            "repo_full_name",
            "pr_number",
            name="uq_pr_lifecycle",
        ),
    )
    op.create_index(
        "ix_pr_lifecycle_installation_id", "pr_lifecycle", ["installation_id"]
    )

    op.create_table(
        "helpful_votes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("vote_type", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "installation_id",
            "repo_full_name",
            "pr_number",
            name="uq_helpful_vote",
        ),
    )
    op.create_index(
        "ix_helpful_votes_installation_id", "helpful_votes", ["installation_id"]
    )

    op.create_table(
        "review_costs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("agent_breakdown", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "installation_id",
            "repo_full_name",
            "pr_number",
            "commit_sha",
            name="uq_review_cost",
        ),
    )
    op.create_index(
        "ix_review_costs_installation_id", "review_costs", ["installation_id"]
    )

    op.create_table(
        "codebase_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("content_chunk", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_embeddings_repo_sha",
        "codebase_embeddings",
        ["repo_full_name", "commit_sha"],
    )
    op.create_index(
        "ix_embeddings_vector",
        "codebase_embeddings",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("codebase_embeddings")
    op.drop_table("review_costs")
    op.drop_table("helpful_votes")
    op.drop_table("pr_lifecycle")
    op.drop_table("installation_fp_insights")
    op.drop_table("finding_dispositions")
    op.drop_table("review_jobs")
    op.drop_table("reviews")
    op.drop_table("installation_settings")
    op.drop_table("installations")
