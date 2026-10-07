"""Scheduler: a simple loop that runs maintenance tasks on a timetable.

Run with:  python -m snapclass.workers.scheduler
Only ONE scheduler should run at a time.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from snapclass.core.logging import setup_logging
from snapclass.core.redis_client import get_redis
from snapclass.workers.maintenance import apply_retention, send_weekly_reports, sweep_stuck_sessions

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
LOOP_SECONDS = 60
RETENTION_EVERY_SECONDS = 3600


def weekly_report_due(now_ist: datetime) -> bool:
    """Monday after 08:00 IST, once per week (remembered in Redis so restarts don't resend)."""
    if now_ist.weekday() != 0 or now_ist.hour < 8:
        return False
    year, week, _ = now_ist.isocalendar()
    # SET NX only succeeds the first time this week → True exactly once.
    return bool(get_redis().set(f"weekly-report:{year}-{week}", "1", nx=True, ex=8 * 24 * 3600))


def run_forever() -> None:
    setup_logging()
    logger.info("Scheduler started")
    last_retention = 0.0
    while True:
        try:
            sweep_stuck_sessions()
            if time.time() - last_retention > RETENTION_EVERY_SECONDS:
                apply_retention()
                last_retention = time.time()
            if weekly_report_due(datetime.now(IST)):
                logger.info("Weekly reports sent", extra={"fields": {"teachers": send_weekly_reports()}})
        except Exception:
            # Never let one bad run stop the scheduler; log it and try again next loop.
            logger.exception("Scheduler task failed")
        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    run_forever()
