from __future__ import annotations

import os
import subprocess
import uuid
import io
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import Response
from scipy.io import wavfile

from .tab.drafts import empty_score, parse_ascii, parse_chords, parse_jianpu, read_draft_file
from .tab.edits import apply_edit
from .tab.gp5 import score_to_gp5_bytes

from .config import Settings
from .schemas import CreateJobResponse, ExportPdfResponse, JobStateResponse
from .security import new_job_token
from .store import JobStore
from .tasks import Runner


def _require_token(store: JobStore, job_id: str, token: Optional[str]) -> None:
    if not token or not store.verify_token(job_id=job_id, token=token):
        raise HTTPException(status_code=401, detail="Invalid or missing job token")


def build_router(*, settings: Settings, store: JobStore, runner: Runner) -> APIRouter:
    r = APIRouter()

    @r.post("/api/jobs", response_model=CreateJobResponse)
    async def create_job(file: UploadFile = File(...)) -> CreateJobResponse:
        filename = file.filename or "input"
        ext = Path(filename).suffix.lower()
        if ext not in {".wav", ".mp3", ".m4a"}:
            raise HTTPException(status_code=400, detail="Upload WAV, MP3, or M4A.")

        job_id = str(uuid.uuid4())
        token = new_job_token()
        store.create_job(job_id=job_id, token=token, ttl_seconds=settings.job_ttl_seconds)

        settings.data_dir.mkdir(parents=True, exist_ok=True)
        job_dir = settings.data_dir / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        content = await file.read()
        max_bytes = settings.max_upload_mb * 1024 * 1024
        if len(content) > max_bytes:
            size_mb = len(content) / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({size_mb:.1f}MB > {settings.max_upload_mb}MB). "
                f"Tip: export mono/16-bit PCM WAV or increase MAX_UPLOAD_MB.",
            )

        in_path = job_dir / filename
        in_path.write_bytes(content)
        try:
            if ext == ".wav":
                sr, data = wavfile.read(str(in_path))
                if sr <= 0:
                    raise ValueError("Invalid sample rate")
                n_frames = int(data.shape[0]) if hasattr(data, "shape") else 0
                duration = n_frames / float(sr)
            else:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(in_path)],
                    capture_output=True,
                    check=True,
                )
                duration = float(probe.stdout.decode().strip() or "0")
            if duration > settings.max_audio_seconds:
                raise HTTPException(
                    status_code=413,
                    detail=f"Audio too long ({duration:.1f}s > {settings.max_audio_seconds}s). "
                    f"Tip: trim audio or increase MAX_AUDIO_SECONDS.",
                )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read that audio file.")

        title = Path(filename).stem or None
        runner.enqueue(job_id, in_path, title)
        return CreateJobResponse(job_id=job_id, job_token=token)

    @r.get("/api/jobs/{job_id}", response_model=JobStateResponse)
    async def get_job_state(job_id: str, x_job_token: Optional[str] = Header(default=None)) -> JobStateResponse:
        _require_token(store, job_id, x_job_token)
        state = store.get_state(job_id=job_id)
        if not state:
            raise HTTPException(status_code=404, detail="Job not found or expired")
        return JobStateResponse(**state)

    @r.get("/api/jobs/{job_id}/result")
    async def get_job_result(job_id: str, x_job_token: Optional[str] = Header(default=None)) -> dict:
        _require_token(store, job_id, x_job_token)
        state = store.get_state(job_id=job_id)
        if not state:
            raise HTTPException(status_code=404, detail="Job not found or expired")
        if state.get("status") != "completed":
            raise HTTPException(status_code=409, detail="Job not completed")
        result = store.get_result(job_id=job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result expired")
        return result

    @r.post("/api/drafts")
    async def create_draft(body: dict[str, Any]) -> dict[str, Any]:
        kind = str(body.get("kind") or "blank")
        text = str(body.get("text") or "")
        if kind == "blank":
            score = empty_score("Blank")
        elif kind == "jianpu":
            score = parse_jianpu(text)
        elif kind == "chords":
            score = parse_chords(text, strum=str(body.get("strum") or "quarter"))
        elif kind == "ascii":
            score = parse_ascii(text)
        else:
            raise HTTPException(status_code=400, detail="Unknown draft kind")
        return {"score": score}

    @r.post("/api/drafts/file")
    async def create_draft_file(file: UploadFile = File(...)) -> dict[str, Any]:
        try:
            score = read_draft_file(file.filename or "draft", await file.read())
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"score": score}

    @r.post("/api/score/edit")
    async def edit_score(body: dict[str, Any]) -> dict[str, Any]:
        try:
            score = apply_edit(body["score"], body["edit"])
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"score": score}

    @r.post("/api/export/gp5")
    async def export_posted_gp5(body: dict[str, Any]) -> Response:
        data = score_to_gp5_bytes(body["score"])
        return Response(content=data, media_type="application/octet-stream")

    @r.get("/api/jobs/{job_id}/export/gp5")
    async def export_gp5(job_id: str, x_job_token: Optional[str] = Header(default=None)) -> Response:
        _require_token(store, job_id, x_job_token)
        state = store.get_state(job_id=job_id)
        if not state:
            raise HTTPException(status_code=404, detail="Job not found or expired")
        if state.get("status") != "completed":
            raise HTTPException(status_code=409, detail="Job not completed")
        result = store.get_result(job_id=job_id)
        if not result or "score" not in result:
            raise HTTPException(status_code=404, detail="Result expired")
        data = score_to_gp5_bytes(result["score"])
        title = str((result.get("score") or {}).get("title") or "tab")
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{title}.gp5"'},
        )

    @r.post("/api/jobs/{job_id}/export/pdf", response_model=ExportPdfResponse)
    async def export_pdf(job_id: str, x_job_token: Optional[str] = Header(default=None)) -> ExportPdfResponse:
        _require_token(store, job_id, x_job_token)
        return ExportPdfResponse(mode="client_print", message="PDF export is handled client-side via browser print.")

    return r
