from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "running", "completed", "failed"]


class CreateJobResponse(BaseModel):
    job_id: str
    job_token: str


class JobStateResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    message: Optional[str] = None
    error: Optional[str] = None


class ExportPdfResponse(BaseModel):
    mode: Literal["client_print"]
    message: str


class AnalysisResult(BaseModel):
    meta: dict[str, Any]
    timeline: dict[str, Any]
    sections: list[dict[str, Any]]
    chords: list[dict[str, Any]]
    rhythm_patterns: list[dict[str, Any]]
    lyrics: Optional[dict[str, Any]] = None
    score: dict[str, Any]
