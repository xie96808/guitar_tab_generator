from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .config import Settings
from .job_runner import run_job
from .store import JobStore


@dataclass(frozen=True)
class Runner:
    enqueue: Callable[[str, Path, Optional[str]], None]


def build_runner(store: JobStore, settings: Settings) -> Runner:
    if settings.redis_url:
        from .celery_tasks import analyze_job

        def enqueue(job_id: str, audio_path: Path, title: Optional[str]) -> None:  # type: ignore[no-redef]
            analyze_job.delay(job_id, str(audio_path), title)

        return Runner(enqueue=enqueue)

    def enqueue(job_id: str, audio_path: Path, title: Optional[str]) -> None:
        t = threading.Thread(target=run_job, args=(store, settings), kwargs={"job_id": job_id, "audio_path": audio_path, "title": title}, daemon=True)
        t.start()

    return Runner(enqueue=enqueue)
