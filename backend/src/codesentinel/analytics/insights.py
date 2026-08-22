"""Analytics — insights rollup for false-positive tracking."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from structlog import get_logger

from codesentinel.config.settings import get_settings
from codesentinel.database.models import utcnow
from codesentinel.database.session import async_session_factory

logger = get_logger()
_settings = get_settings()


async def run_insight_rollup() -> dict:
    """Compute FP insight rollups for all installations."""
    windows = ["7d", "30d", "90d"]
    now = utcnow()
    results = {"installations": 0, "rollups": 0}

    async with async_session_factory() as session:
        installations = await session.execute(
            text("SELECT DISTINCT installation_id FROM installations")
        )
        installation_ids = [row[0] for row in installations.fetchall()]

    for installation_id in installation_ids:
        for window in windows:
            days = int(window.rstrip("d"))
            since = now - timedelta(days=days)

            async with async_session_factory() as session:
                total = await session.execute(
                    text(
                        "SELECT count(*) FROM finding_dispositions "
                        "WHERE installation_id = :id AND last_seen_at >= :since"
                    ),
                    {"id": installation_id, "since": since},
                )
                total_findings = total.scalar() or 0

                disputed = await session.execute(
                    text(
                        "SELECT count(*) FROM finding_dispositions "
                        "WHERE installation_id = :id AND dispute_count > 0 "
                        "AND last_seen_at >= :since"
                    ),
                    {"id": installation_id, "since": since},
                )
                disputed_findings = disputed.scalar() or 0

                resolved = await session.execute(
                    text(
                        "SELECT count(*) FROM finding_dispositions "
                        "WHERE installation_id = :id AND resolve_count > 0 "
                        "AND last_seen_at >= :since"
                    ),
                    {"id": installation_id, "since": since},
                )
                resolved_findings = resolved.scalar() or 0

                quiet = await session.execute(
                    text(
                        "SELECT count(*) FROM finding_dispositions "
                        "WHERE installation_id = :id AND silent_drop_count > 0 "
                        "AND last_seen_at >= :since"
                    ),
                    {"id": installation_id, "since": since},
                )
                quiet_drops = quiet.scalar() or 0

                category_rates = await session.execute(
                    text("""
                        SELECT category,
                               count(*) as total,
                               count(*) FILTER (WHERE dispute_count > 0) as disputed
                        FROM finding_dispositions
                        WHERE installation_id = :id AND last_seen_at >= :since
                        GROUP BY category
                    """),
                    {"id": installation_id, "since": since},
                )
                rates = {
                    row[0]: {
                        "total": row[1],
                        "disputed": row[2],
                        "rate": row[2] / row[1] if row[1] > 0 else 0,
                    }
                    for row in category_rates.fetchall()
                    if row[0]
                }

                await session.execute(
                    text("""
                        INSERT INTO installation_fp_insights
                            (installation_id, "window", total_findings,
                             disputed_findings, resolved_findings, quiet_drops,
                             category_dispute_rates, computed_at)
                        VALUES (:id, :window, :total, :disputed, :resolved,
                                :quiet, :rates, :now)
                        ON CONFLICT (installation_id, "window")
                        DO UPDATE SET
                            total_findings = EXCLUDED.total_findings,
                            disputed_findings = EXCLUDED.disputed_findings,
                            resolved_findings = EXCLUDED.resolved_findings,
                            quiet_drops = EXCLUDED.quiet_drops,
                            category_dispute_rates = EXCLUDED.category_dispute_rates,
                            computed_at = EXCLUDED.computed_at
                    """),
                    {
                        "id": installation_id,
                        "window": window,
                        "total": total_findings,
                        "disputed": disputed_findings,
                        "resolved": resolved_findings,
                        "quiet": quiet_drops,
                        "rates": str(rates),
                        "now": now,
                    },
                )
                await session.commit()
                results["rollups"] += 1

        results["installations"] += 1

    logger.info("insight_rollup_complete", **results)
    return results


async def start_insights_cron() -> None:
    """Start the insights rollup scheduler."""
    import asyncio

    interval = _settings.insights_rollup_interval_minutes * 60
    initial_delay = 60

    logger.info(
        "insights_cron_starting",
        interval_minutes=_settings.insights_rollup_interval_minutes,
        initial_delay=initial_delay,
    )

    await asyncio.sleep(initial_delay)

    while True:
        try:
            await run_insight_rollup()
        except Exception as e:
            logger.error("insights_cron_error", error=str(e))
        await asyncio.sleep(interval)
