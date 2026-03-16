from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "ps13_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "run-due-ingestion-sources": {
            "task": "app.tasks.jobs.run_due_ingestion_sources_job",
            "schedule": settings.live_poll_scheduler_seconds,
        },
        "run-federation-periodic": {
            "task": "app.tasks.jobs.run_federation_job",
            "schedule": settings.federation_scheduler_seconds,
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks.jobs"])
