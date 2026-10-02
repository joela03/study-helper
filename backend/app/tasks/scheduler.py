"""
Scheduled tasks using APScheduler.
Handles daily reminders and periodic maintenance.
"""
import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def get_due_cards_summary() -> dict:
    """Get summary of due cards per profile."""
    from app.models.card import Card
    from app.models.profile import SubjectProfile

    engine = create_engine(settings.DATABASE_URL)

    with Session(engine) as db:
        today = date.today()

        # Get profiles with due card counts
        results = db.execute(
            select(
                SubjectProfile.id,
                SubjectProfile.name,
                func.count(Card.id).label("due_count")
            )
            .join(Card, Card.profile_id == SubjectProfile.id)
            .where(Card.next_review <= today)
            .group_by(SubjectProfile.id, SubjectProfile.name)
        ).all()

        return {
            "date": str(today),
            "profiles": [
                {"id": r.id, "name": r.name, "due_count": r.due_count}
                for r in results
            ],
            "total_due": sum(r.due_count for r in results),
        }


def send_daily_reminder():
    """
    Daily reminder task - runs at configured time.

    For now, logs the reminder. In production, this would:
    - Send email notifications
    - Push notifications
    - Webhook to external service
    """
    summary = get_due_cards_summary()

    if summary["total_due"] == 0:
        logger.info("Daily reminder: No cards due today!")
        return

    logger.info(f"Daily reminder: {summary['total_due']} cards due today")
    for profile in summary["profiles"]:
        logger.info(f"  - {profile['name']}: {profile['due_count']} cards")

    # TODO: Integrate with notification service
    # - Email via SendGrid/SES
    # - Push via Firebase
    # - Webhook to Slack/Discord


def start_scheduler():
    """Start the APScheduler with configured jobs."""
    if scheduler.running:
        return

    # Daily reminder at 8:00 AM
    scheduler.add_job(
        send_daily_reminder,
        CronTrigger(hour=8, minute=0),
        id="daily_reminder",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with daily reminder at 8:00 AM")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
