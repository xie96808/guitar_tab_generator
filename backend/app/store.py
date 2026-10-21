from __future__ import annotations

import json
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional, Protocol

from .security import hash_token


class JobStore(Protocol):
    def create_job(self, *, job_id: str, token: str, ttl_seconds: int) -> None: ...
    def verify_token(self, *, job_id: str, token: str) -> bool: ...
    def get_state(self, *, job_id: str) -> Optional[dict[str, Any]]: ...
    def update_state(self, *, job_id: str, patch: dict[str, Any]) -> None: ...
    def set_result(self, *, job_id: str, result: dict[str, Any]) -> None: ...
    def get_result(self, *, job_id: str) -> Optional[dict[str, Any]]: ...


@dataclass
class _MemJob:
    token_hash: str
    expires_at: float
    state: dict[str, Any]
    result: Optional[dict[str, Any]] = None


class MemoryJobStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, _MemJob] = {}

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [job_id for job_id, job in self._jobs.items() if job.expires_at <= now]
        for job_id in expired:
            self._jobs.pop(job_id, None)

    def create_job(self, *, job_id: str, token: str, ttl_seconds: int) -> None:
        with self._lock:
            self._purge_expired()
            self._jobs[job_id] = _MemJob(
                token_hash=hash_token(token),
                expires_at=time.time() + ttl_seconds,
                state={"job_id": job_id, "status": "queued", "progress": 0, "message": "Queued"},
            )

    def verify_token(self, *, job_id: str, token: str) -> bool:
        with self._lock:
            self._purge_expired()
            job = self._jobs.get(job_id)
            if not job:
                return False
            return job.token_hash == hash_token(token)

    def get_state(self, *, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            self._purge_expired()
            job = self._jobs.get(job_id)
            return dict(job.state) if job else None

    def update_state(self, *, job_id: str, patch: dict[str, Any]) -> None:
        with self._lock:
            self._purge_expired()
            job = self._jobs.get(job_id)
            if not job:
                return
            job.state.update(patch)

    def set_result(self, *, job_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            self._purge_expired()
            job = self._jobs.get(job_id)
            if not job:
                return
            job.result = json.loads(json.dumps(result))

    def get_result(self, *, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            self._purge_expired()
            job = self._jobs.get(job_id)
            return dict(job.result) if (job and job.result) else None


class RedisJobStore:
    def __init__(self, redis_url: str) -> None:
        import redis  # type: ignore

        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def _job_key(self, job_id: str) -> str:
        return f"job:{job_id}"

    def _result_key(self, job_id: str) -> str:
        return f"job:{job_id}:result"

    def create_job(self, *, job_id: str, token: str, ttl_seconds: int) -> None:
        key = self._job_key(job_id)
        now = int(time.time())
        self._redis.hset(
            key,
            mapping={
                "job_id": job_id,
                "token_hash": hash_token(token),
                "status": "queued",
                "progress": "0",
                "message": "Queued",
                "created_at": str(now),
            },
        )
        self._redis.expire(key, ttl_seconds)

    def verify_token(self, *, job_id: str, token: str) -> bool:
        key = self._job_key(job_id)
        token_hash = self._redis.hget(key, "token_hash")
        return bool(token_hash) and token_hash == hash_token(token)

    def get_state(self, *, job_id: str) -> Optional[dict[str, Any]]:
        key = self._job_key(job_id)
        data = self._redis.hgetall(key)
        if not data:
            return None
        data["progress"] = int(data.get("progress") or 0)
        data.pop("token_hash", None)
        return data

    def update_state(self, *, job_id: str, patch: dict[str, Any]) -> None:
        key = self._job_key(job_id)
        patch2 = {k: (str(v) if not isinstance(v, str) else v) for k, v in patch.items()}
        self._redis.hset(key, mapping=patch2)

    def set_result(self, *, job_id: str, result: dict[str, Any]) -> None:
        key = self._result_key(job_id)
        self._redis.set(key, json.dumps(result, ensure_ascii=False), ex=3600)

    def get_result(self, *, job_id: str) -> Optional[dict[str, Any]]:
        key = self._result_key(job_id)
        raw = self._redis.get(key)
        return json.loads(raw) if raw else None
