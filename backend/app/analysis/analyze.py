from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from ..tab.transcribe import transcribe_audio
from .audio import ProgressCb, analyze_primitives
from .capo import capo_suggestion
from .chords import estimate_chords_per_beat
from .key import detect_key
from .rhythm import accent_from_hits, beats_to_measures, cluster_mode_pattern, map_onsets_to_hitmask, suggest_du
from .sections import detect_sections


def analyze_audio_file(path: Path, *, title: Optional[str], progress: ProgressCb) -> dict:
    path = Path(path)
    if path.suffix.lower() != ".wav":
        decoded = path.with_suffix(".decoded.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), "-ac", "1", "-ar", "22050", str(decoded)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            return analyze_audio_file(decoded, title=title, progress=progress)
        finally:
            decoded.unlink(missing_ok=True)
    primitives = analyze_primitives(path, progress)
    tempo_bpm = float(primitives["tempo_bpm"])
    beat_times = np.array(primitives["beat_times"], dtype=np.float32)
    onset_times = np.array(primitives["onset_times"], dtype=np.float32)
    chroma_beat = np.array(primitives["chroma_beat"], dtype=np.float32)

    progress(50, "Detecting key…")
    key_info = detect_key(chroma_beat)

    progress(55, "Estimating chords…")
    chords = estimate_chords_per_beat(chroma_beat, key_pcs=key_info["pcs"])

    # MVP default meter is 4/4. Frontend may override to regroup beats.
    beats_per_bar = 4
    measures = beats_to_measures(beat_times, beats_per_bar=beats_per_bar)

    progress(70, "Detecting sections…")
    sections = detect_sections(chroma_beat, beats_per_bar=beats_per_bar)

    progress(80, "Extracting rhythm patterns…")
    subdivisions_per_bar = 16
    rhythm_patterns = []
    for sec in sections:
        masks = []
        for m in measures[sec.start_measure : sec.end_measure + 1]:
            mask = map_onsets_to_hitmask(
                onset_times,
                m["start_time"],
                m["end_time"],
                subdivisions_per_bar=subdivisions_per_bar,
            )
            masks.append(mask)
        mode = cluster_mode_pattern(masks)
        accent = accent_from_hits(mode, beats_per_bar=beats_per_bar)
        rhythm_patterns.append(
            {
                "section_id": sec.id,
                "subdivisions_per_bar": subdivisions_per_bar,
                "hit_mask": mode.astype(int).tolist(),
                "accent": accent.astype(int).tolist(),
                "style": "strum",
                "suggested_du": suggest_du(mode, beats_per_bar=beats_per_bar),
            }
        )

    progress(90, "Suggesting capo/transpose…")
    uniq_chords = [c.chord for c in chords]
    capo = capo_suggestion(uniq_chords)

    progress(100, "Done")
    return {
        "meta": {
            "title": title or "Untitled",
            "bpm": tempo_bpm,
            "time_signature": "4/4",
            "key": f'{key_info["key"]} {key_info["mode"]}',
            "key_confidence": float(key_info["confidence"]),
            "suggested_capo": capo,
            "limitations": [
                "MVP meter defaults to 4/4. Use the editor to override meter if needed.",
                "Fallback analyzer supports WAV best (ffmpeg/librosa not bundled).",
                "Transcription is a draft of a single guitar line. Edit the frets before exporting.",
            ],
        },
        "timeline": {
            "beat_times": beat_times.tolist(),
            "onset_times": onset_times.tolist(),
            "measures": measures,
        },
        "sections": [{"id": s.id, "name": s.name, "start_measure": s.start_measure, "end_measure": s.end_measure} for s in sections],
        "chords": [{"beat_index": c.beat_index, "chord": c.chord, "confidence": c.confidence} for c in chords],
        "rhythm_patterns": rhythm_patterns,
        "lyrics": None,
        "score": transcribe_audio(path, title=title),
    }
