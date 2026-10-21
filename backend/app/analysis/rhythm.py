from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RhythmPattern:
    section_id: str
    subdivisions_per_bar: int
    hit_mask: list[int]
    accent: list[int]
    style: str
    suggested_du: list[str]


def beats_to_measures(beat_times: np.ndarray, *, beats_per_bar: int) -> list[dict]:
    measures = []
    n_beats = len(beat_times)
    n_bars = max(1, n_beats // beats_per_bar)
    for m in range(n_bars):
        b0 = m * beats_per_bar
        b1 = min(n_beats, (m + 1) * beats_per_bar)
        t0 = float(beat_times[b0]) if b0 < n_beats else float(beat_times[-1])
        t1 = float(beat_times[b1]) if b1 < n_beats else float(beat_times[-1] + (beat_times[-1] - beat_times[-2] if n_beats > 1 else 0.5))
        measures.append(
            {
                "index": m,
                "start_time": t0,
                "end_time": t1,
                "beats_per_bar": beats_per_bar,
            }
        )
    return measures


def map_onsets_to_hitmask(
    onset_times: np.ndarray,
    measure_start: float,
    measure_end: float,
    *,
    subdivisions_per_bar: int,
) -> np.ndarray:
    mask = np.zeros((subdivisions_per_bar,), dtype=np.int32)
    dur = max(1e-6, measure_end - measure_start)
    for t in onset_times:
        if t < measure_start or t >= measure_end:
            continue
        pos = (float(t) - measure_start) / dur
        idx = int(round(pos * (subdivisions_per_bar - 1)))
        idx = max(0, min(subdivisions_per_bar - 1, idx))
        mask[idx] = 1
    return mask


def cluster_mode_pattern(masks: list[np.ndarray]) -> np.ndarray:
    if not masks:
        return np.zeros((16,), dtype=np.int32)
    uniq: dict[bytes, int] = {}
    for m in masks:
        key = m.astype(np.int8).tobytes()
        uniq[key] = uniq.get(key, 0) + 1
    best = max(uniq.items(), key=lambda kv: kv[1])[0]
    out = np.frombuffer(best, dtype=np.int8).astype(np.int32)
    return out


def accent_from_hits(hit_mask: np.ndarray, *, beats_per_bar: int) -> np.ndarray:
    subdiv = len(hit_mask)
    accent = np.zeros_like(hit_mask)
    if beats_per_bar <= 0:
        return accent
    per_beat = max(1, subdiv // beats_per_bar)
    for b in range(beats_per_bar):
        accent[b * per_beat] = 1
    return accent


def suggest_du(hit_mask: np.ndarray, *, beats_per_bar: int) -> list[str]:
    subdiv = len(hit_mask)
    per_beat = max(1, subdiv // beats_per_bar)
    out = [""] * subdiv
    for i in range(subdiv):
        if hit_mask[i] == 0:
            continue
        is_onbeat = (i % per_beat) == 0
        out[i] = "D" if is_onbeat else "U"
    return out

