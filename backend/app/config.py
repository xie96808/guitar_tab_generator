from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Settings:
    redis_url: Optional[str]
    job_ttl_seconds: int
    data_dir: Path
    max_audio_seconds: int
    max_upload_mb: int


def load_settings() -> Settings:
    redis_url = os.getenv("REDIS_URL") or None
    job_ttl_seconds = int(os.getenv("JOB_TTL_SECONDS", "3600"))
    max_audio_seconds = int(os.getenv("MAX_AUDIO_SECONDS", "300"))
    max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "50"))
    data_dir = Path(os.getenv("JOB_DATA_DIR", Path(__file__).resolve().parent.parent / ".data")).resolve()
    return Settings(
        redis_url=redis_url,
        job_ttl_seconds=job_ttl_seconds,
        data_dir=data_dir,
        max_audio_seconds=max_audio_seconds,
        max_upload_mb=max_upload_mb,
    )
