from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "study_helper",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    # Declared explicitly: autodiscover_tasks looks for a submodule *named*
    # "tasks" (i.e. app.tasks.tasks), which does not exist here, so the
    # worker started with an empty registry and discarded every message.
    include=["app.tasks.transcription"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max for transcription tasks
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])
