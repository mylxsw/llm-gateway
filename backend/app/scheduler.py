"""
Scheduled Task Module

Uses APScheduler to manage scheduled tasks, such as log cleanup and KV store cleanup.
"""

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.db.session import get_db
from app.repositories.sqlalchemy.kv_store_repo import SQLAlchemyKVStoreRepository
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


async def cleanup_expired_kv_task():
    """
    Scheduled KV Store Cleanup Task

    Deletes expired key-value pairs.
    """
    logger.info("Starting scheduled KV store cleanup task")

    try:
        async for db in get_db():
            kv_repo = SQLAlchemyKVStoreRepository(db)
            deleted_count = await kv_repo.cleanup_expired()
            logger.info(
                f"KV store cleanup task completed: {deleted_count} expired keys deleted"
            )
            break

    except Exception as e:
        logger.error(f"KV store cleanup task failed: {str(e)}", exc_info=True)


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

    # Add log cleanup task (Executes every configured interval)
    _scheduler.add_job(
        cleanup_logs_task,
        trigger=IntervalTrigger(hours=settings.LOG_CLEANUP_INTERVAL_HOURS),
        id="cleanup_old_logs",
        name="Clean up old logs",
        replace_existing=True,
    )

    # Add KV store cleanup task (Executes daily at 1:00 AM)
    # Skip when using Redis as KV backend since Redis manages TTL natively
    if settings.KV_STORE_TYPE != "redis":
        _scheduler.add_job(
            cleanup_expired_kv_task,
            trigger=CronTrigger(hour=1, minute=0),
            id="cleanup_expired_kv",
            name="Clean up expired KV pairs",
            replace_existing=True,
        )

    # Start scheduler
    _scheduler.start()

    kv_cleanup_msg = (
        ", KV store cleanup scheduled daily at 1:00"
        if settings.KV_STORE_TYPE != "redis"
        else ", KV store cleanup skipped (using Redis)"
    )
    logger.info(
        "Scheduler started: log cleanup scheduled every "
        f"{settings.LOG_CLEANUP_INTERVAL_HOURS} hours"
        + kv_cleanup_msg
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
