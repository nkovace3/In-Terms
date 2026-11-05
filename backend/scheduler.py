import asyncio
import logging
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from config import get_settings
from logging_config import configure_logging
from services.pipeline import run_ingestion

configure_logging()
logger = logging.getLogger(__name__)

scheduler = BlockingScheduler()

@scheduler.scheduled_job(
    "interval",
    minutes=get_settings().ingestion_interval_minutes,
    # Run once immediately on startup instead of waiting a full interval,
    # so a fresh deploy has new articles right away.
    next_run_time=datetime.now(),
    # A run can outlast the interval (each article is ~a dozen LLM calls).
    # Never overlap runs, and collapse any missed ones into a single run.
    max_instances=1,
    coalesce=True,
)
def scheduled_ingestion():
    logger.info("Starting scheduled ingestion")
    asyncio.run(run_ingestion())
    logger.info("Scheduled ingestion complete")

def run_once() -> int:
    """
    Single ingestion run for an external scheduler (GitHub Actions cron).
    Exits non-zero if any feed or article failed, so the run shows up red
    and GitHub emails a failure notice — that's the alerting.
    """
    results = asyncio.run(run_ingestion())
    problems = [r for r in results if r.error or r.failed]
    return 1 if problems else 0

if __name__ == '__main__':
    if "--once" in sys.argv:
        sys.exit(run_once())

    logger.info(
        "Scheduler started (every %d min)", get_settings().ingestion_interval_minutes
    )
    scheduler.start()
