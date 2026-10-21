from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import build_router
from .config import load_settings
from .store import MemoryJobStore, RedisJobStore
from .tasks import build_runner


def create_app() -> FastAPI:
    settings = load_settings()
    if settings.redis_url:
        store = RedisJobStore(settings.redis_url)
    else:
        store = MemoryJobStore()
    runner = build_runner(store, settings)

    app = FastAPI(title="Guitar Tab Generator (MVP)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_router(settings=settings, store=store, runner=runner))
    return app


app = create_app()

