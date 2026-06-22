from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from main import generate_daily_report
from utils.logger import setup_logger


logger = setup_logger("xauusd_scheduler")


def start_scheduler() -> None:
    hour, minute = [int(part) for part in settings.report_time.split(":", maxsplit=1)]
    scheduler = BlockingScheduler(timezone=settings.timezone)
    scheduler.add_job(
        generate_daily_report,
        CronTrigger(hour=hour, minute=minute, timezone=settings.timezone),
        id="daily_xauusd_report",
        replace_existing=True,
        kwargs={"send_telegram": True},
    )
    logger.info(
        "Scheduler started. Daily run time: %s %s",
        settings.report_time,
        settings.timezone,
    )
    scheduler.start()


if __name__ == "__main__":
    start_scheduler()
