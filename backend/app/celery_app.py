from __future__ import annotations

import os

from celery import Celery


def _redis_url() -> str:
    url = os.getenv("REDIS_URL")
    if not url:
        raise RuntimeError("REDIS_URL is required to run Celery worker")
    return url


celery_app = Celery("guitar_tab_generator", broker=_redis_url(), backend=_redis_url())
celery_app.conf.task_track_started = True

