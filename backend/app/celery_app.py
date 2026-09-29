from celery import Celery

from app.config import settings

celery_app = Celery(
    "knowledge_assistant",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.indexing"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
