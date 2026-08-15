"""Celery application — task broker and beat scheduler."""
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "linkedin_intelligence",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.worker.tasks.market",
        "app.worker.tasks.email",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Argentina/Buenos_Aires",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        # Nightly market snapshot at 2 AM ART
        "nightly-market-snapshot": {
            "task": "app.worker.tasks.market.snapshot_all_roles",
            "schedule": crontab(hour=2, minute=0),
        },
        # Weekly digest email every Monday at 8 AM ART
        "weekly-digest": {
            "task": "app.worker.tasks.email.send_weekly_digests",
            "schedule": crontab(day_of_week=1, hour=8, minute=0),
        },
    },
)
