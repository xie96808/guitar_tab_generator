from __future__ import annotations

import traceback
from pathlib import Path
from typing import Callable, Optional

from .analysis.analyze import analyze_audio_file
from .config import Settings
from .store import JobStore


def _progress_updater(store: JobStore, job_id: str) -> Callable[[int, str], None]:
    def cb(p: int, msg: str) -> None:
        store.update_state(job_id=job_id, patch={"status": "running", "progress": int(p), "message": msg})

    return cb


def run_job(store: JobStore, settings: Settings, *, job_id: str, audio_path: Path, title: Optional[str]) -> None:
    try:
        store.update_state(job_id=job_id, patch={"status": "running", "progress": 0, "message": "Starting"})
        result = analyze_audio_file(audio_path, title=title, progress=_progress_updater(store, job_id))
        store.set_result(job_id=job_id, result=result)
        store.update_state(job_id=job_id, patch={"status": "completed", "progress": 100, "message": "Completed"})
    except Exception as e:  # noqa: BLE001
        store.update_state(
            job_id=job_id,
            patch={
                "status": "failed",
                "progress": 100,
                "message": "Failed",
                "error": f"{e}\n{traceback.format_exc()}",
            },
        )

