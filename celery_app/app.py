import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "portintel",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "celery_app.tasks.risk_scoring",
        "celery_app.tasks.weather_poller",
        "celery_app.tasks.congestion",
        "celery_app.tasks.alerts",
    ],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)

app.conf.beat_schedule = {
    # Score risk for all active vessels every 10 minutes
    "score-all-active-vessels": {
        "task": "celery_app.tasks.risk_scoring.score_all_active_vessels",
        "schedule": 600,  # seconds
    },
    # Poll weather every 30 minutes
    "poll-weather": {
        "task": "celery_app.tasks.weather_poller.poll_all_regions",
        "schedule": 1800,
    },
    # Compute port congestion every 15 minutes
    "compute-port-congestion": {
        "task": "celery_app.tasks.congestion.compute_all_ports",
        "schedule": 900,
    },
}
