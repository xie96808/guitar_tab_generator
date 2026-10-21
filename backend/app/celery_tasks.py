from __future__ import annotations

from pathlib import Path
from typing import Optional

from .celery_app import celery_app
from .config import load_settings
from .job_runner import run_job
from .store import RedisJobStore


@celery_app.task(name="analyze_job")
def analyze_job(job_id: str, audio_path: str, title: Optional[str] = None) -> None:
    settings = load_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required for analyze_job")
    store = RedisJobStore(settings.redis_url)
    run_job(store, settings, job_id=job_id, audio_path=Path(audio_path), title=title)

