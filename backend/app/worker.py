"""Celery worker application."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "linkedin_intelligence",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.crawler.runner",
        "app.etl.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

# Alias expected by docker-compose: celery -A app.worker
app = celery_app
