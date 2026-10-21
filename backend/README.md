# Backend (FastAPI + optional Celery/Redis)

## Quickstart (local, no Redis)
This mode runs analysis in a background thread (no queue).

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

## Recommended (Celery + Redis)
1) Start Redis (example command if you have it installed):

```bash
redis-server
```

2) Start API + worker:

```bash
cd backend
export REDIS_URL="redis://localhost:6379/0"
uvicorn app.main:app --reload --port 8000
celery -A app.celery_app.celery_app worker -l info
```

## Notes
- If `ffmpeg` is available, the backend can accept more audio formats; otherwise, the built-in fallback only supports WAV reliably.
- WAV can be PCM (int) or IEEE float. If you hit upload limits, re-export as **mono 16-bit PCM** to reduce file size.
- Jobs are ephemeral. The client holds a `job_token` in memory; closing the page loses access.
