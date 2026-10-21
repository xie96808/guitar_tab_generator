from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Section:
    id: str
    name: str
    start_measure: int
    end_measure: int


def _bar_chroma(chroma_beat: np.ndarray, beats_per_bar: int) -> np.ndarray:
    n_beats = chroma_beat.shape[1]
    n_bars = max(1, n_beats // beats_per_bar)
    bars = []
    for i in range(n_bars):
        b0 = i * beats_per_bar
        b1 = min(n_beats, (i + 1) * beats_per_bar)
        v = chroma_beat[:, b0:b1].mean(axis=1)
        v = v / (np.linalg.norm(v) + 1e-6)
        bars.append(v)
    return np.stack(bars, axis=1)


def detect_sections(chroma_beat: np.ndarray, *, beats_per_bar: int) -> list[Section]:
    bars = _bar_chroma(chroma_beat, beats_per_bar)
    n_bars = bars.shape[1]
    if n_bars <= 4:
        return [Section(id="A", name="A", start_measure=0, end_measure=n_bars - 1)]

    diffs = np.linalg.norm(np.diff(bars, axis=1), axis=0)
    if diffs.size == 0:
        return [Section(id="A", name="A", start_measure=0, end_measure=n_bars - 1)]

    thresh = float(np.median(diffs) + np.std(diffs))
    boundaries = [0]
    for i, d in enumerate(diffs, start=1):
        if float(d) > thresh:
            boundaries.append(i)
    boundaries.append(n_bars)
    boundaries = sorted(set(boundaries))

    segments: list[tuple[int, int, np.ndarray]] = []
    for s, e in zip(boundaries[:-1], boundaries[1:]):
        if e - s <= 0:
            continue
        mean = bars[:, s:e].mean(axis=1)
        mean = mean / (np.linalg.norm(mean) + 1e-6)
        segments.append((s, e, mean))

    names = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    labeled: list[Section] = []
    centroids: list[np.ndarray] = []
    for (s, e, mean) in segments:
        assigned = None
        for idx, c in enumerate(centroids):
            if float(np.dot(mean, c)) >= 0.92:
                assigned = idx
                break
        if assigned is None:
            centroids.append(mean)
            assigned = len(centroids) - 1
        name = names[assigned] if assigned < len(names) else f"S{assigned+1}"
        labeled.append(Section(id=name, name=name, start_measure=s, end_measure=e - 1))

    if not labeled:
        return [Section(id="A", name="A", start_measure=0, end_measure=n_bars - 1)]
    return labeled

