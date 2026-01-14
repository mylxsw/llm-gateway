"""
Scheduled Task Module

Uses APScheduler to manage scheduled tasks, such as log cleanup.
"""

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.db.session import get_db
from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository
from app.services.log_service import LogService

logger = logging.getLogger(__name__)

# Global Scheduler Instance
_scheduler: Optional[AsyncIOScheduler] = None


async def cleanup_logs_task():
    """
    Scheduled Log Cleanup Task

    Deletes log records exceeding the retention period.
    """
    settings = get_settings()
    logger.info(
        f"Starting scheduled log cleanup task (retention: {settings.LOG_RETENTION_DAYS} days)"
    )

    try:
        # Get database session
        async for db in get_db():
            # Create service instance
            log_repo = SQLAlchemyLogRepository(db)
            log_service = LogService(log_repo)

            # Execute cleanup
            deleted_count = await log_service.cleanup_old_logs(
                settings.LOG_RETENTION_DAYS
            )
            logger.info(f"Log cleanup task completed: {deleted_count} logs deleted")
            break  # Only one iteration needed

    except Exception as e:
        logger.error(f"Log cleanup task failed: {str(e)}", exc_info=True)


def start_scheduler():
    """
    Start Scheduled Task Scheduler

    Initializes the scheduler and adds all scheduled tasks.
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler already started")
        return

    settings = get_settings()

    # Create scheduler
    _scheduler = AsyncIOScheduler()

    # Add log cleanup task (Executes daily at configured time)
    _scheduler.add_job(
        cleanup_logs_task,
        trigger=CronTrigger(hour=settings.LOG_CLEANUP_HOUR, minute=0),
        id="cleanup_old_logs",
        name="Clean up old logs",
        replace_existing=True,
    )

    # Start scheduler
    _scheduler.start()
    logger.info(
        f"Scheduler started: log cleanup scheduled daily at {settings.LOG_CLEANUP_HOUR}:00"
    )


def shutdown_scheduler():
    """
    Shutdown Scheduled Task Scheduler

    Gracefully stops all scheduled tasks.
    """
    global _scheduler

    if _scheduler is None:
        return

    _scheduler.shutdown(wait=True)
    _scheduler = None
    logger.info("Scheduler shutdown completed")


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """
    Get Scheduler Instance

    Returns:
        Optional[AsyncIOScheduler]: Scheduler instance or None
    """
    return _scheduler