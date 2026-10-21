from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def fixture_path() -> Path:
    return Path(__file__).resolve().parents[3] / "scores" / "fixture.score.json"


def load_fixture_score() -> dict[str, Any]:
    score = json.loads(fixture_path().read_text(encoding="utf-8"))
    validate_score(score)
    return score


def validate_score(score: dict[str, Any]) -> None:
    tracks = score.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("score.tracks is required")
    for track in tracks:
        for bar in track.get("bars") or []:
            for beat in bar.get("beats") or []:
                if "duration" not in beat:
                    raise ValueError("beat.duration is required")
                notes = beat.get("notes") or []
                if not notes and not beat.get("rest"):
                    raise ValueError("beat.notes is required")
                for note in notes:
                    for key in ("string", "fret", "duration"):
                        if key not in note:
                            raise ValueError(f"note.{key} is required")


def iter_beats(score: dict[str, Any]) -> list[dict[str, Any]]:
    beats: list[dict[str, Any]] = []
    for track in score["tracks"]:
        for bar in track["bars"]:
            for beat in bar["beats"]:
                if beat.get("rest") or not beat.get("notes"):
                    continue
                duration = float(beat["duration"])
                notes = sorted(
                    (
                        {
                            "string": int(note["string"]),
                            "fret": int(note["fret"]),
                            "duration": float(note["duration"]),
                        }
                        for note in beat["notes"]
                    ),
                    key=lambda note: note["string"],
                )
                beats.append({"duration": duration, "notes": notes})
    return beats
