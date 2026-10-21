from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass(frozen=True)
class ChordEvent:
    beat_index: int
    chord: str
    confidence: float


def _template_for(root_pc: int, quality: str) -> tuple[str, np.ndarray, list[int]]:
    tpl = np.zeros((12,), dtype=np.float32)
    pcs: list[int] = []
    if quality == "maj":
        intervals = [0, 4, 7]
        weights = [1.0, 0.85, 0.75]
        name = f"{NOTE_NAMES_SHARP[root_pc]}"
    elif quality == "min":
        intervals = [0, 3, 7]
        weights = [1.0, 0.85, 0.75]
        name = f"{NOTE_NAMES_SHARP[root_pc]}m"
    elif quality == "7":
        intervals = [0, 4, 7, 10]
        weights = [1.0, 0.85, 0.75, 0.65]
        name = f"{NOTE_NAMES_SHARP[root_pc]}7"
    elif quality == "maj7":
        intervals = [0, 4, 7, 11]
        weights = [1.0, 0.85, 0.75, 0.65]
        name = f"{NOTE_NAMES_SHARP[root_pc]}maj7"
    elif quality == "min7":
        intervals = [0, 3, 7, 10]
        weights = [1.0, 0.85, 0.75, 0.65]
        name = f"{NOTE_NAMES_SHARP[root_pc]}m7"
    elif quality == "sus4":
        intervals = [0, 5, 7]
        weights = [1.0, 0.8, 0.75]
        name = f"{NOTE_NAMES_SHARP[root_pc]}sus4"
    else:
        raise ValueError(f"Unsupported quality: {quality}")
    for i, w in zip(intervals, weights):
        pc = (root_pc + i) % 12
        tpl[pc] = float(w)
        pcs.append(pc)
    tpl /= np.linalg.norm(tpl) + 1e-6
    return (name, tpl, pcs)


ChordTemplate = tuple[str, np.ndarray, list[int]]

TEMPLATES: list[ChordTemplate] = []
for root in range(12):
    for q in ("maj", "min", "7", "maj7", "min7", "sus4"):
        TEMPLATES.append(_template_for(root, q))


def _viterbi_best_path(emission: np.ndarray, transition: np.ndarray) -> np.ndarray:
    # emission: (T, S) higher is better; transition: (S, S) higher is better
    T, S = emission.shape
    dp = np.full((T, S), -1e9, dtype=np.float32)
    back = np.zeros((T, S), dtype=np.int32)
    dp[0] = emission[0]
    for t in range(1, T):
        scores = dp[t - 1][:, None] + transition
        back[t] = np.argmax(scores, axis=0)
        dp[t] = emission[t] + scores[back[t], np.arange(S)]
    path = np.zeros((T,), dtype=np.int32)
    path[-1] = int(np.argmax(dp[-1]))
    for t in range(T - 2, -1, -1):
        path[t] = back[t + 1, path[t + 1]]
    return path


def estimate_chords_per_beat(chroma_beat: np.ndarray, *, key_pcs: Optional[set[int]] = None) -> list[ChordEvent]:
    events: list[ChordEvent] = []
    S = len(TEMPLATES)
    T = chroma_beat.shape[1]
    if T == 0:
        return []

    emission = np.zeros((T, S), dtype=np.float32)
    for t in range(T):
        v = chroma_beat[:, t].astype(np.float32)
        v /= np.linalg.norm(v) + 1e-6
        for s, (_, tpl, pcs) in enumerate(TEMPLATES):
            score = float(np.dot(v, tpl))
            if key_pcs is not None:
                out_of_key = sum((pc not in key_pcs) for pc in pcs)
                score -= 0.06 * float(out_of_key)
            emission[t, s] = score

    # Transition prefers staying, and small root motion.
    transition = np.zeros((S, S), dtype=np.float32)
    roots = np.array([i // 6 for i in range(S)], dtype=np.int32)  # 6 qualities per root in insertion order
    for i in range(S):
        for j in range(S):
            if i == j:
                transition[i, j] = 0.12
            else:
                di = int(abs(int(roots[i]) - int(roots[j])))
                di = min(di, 12 - di)
                transition[i, j] = -0.08 - 0.015 * float(di)

    path = _viterbi_best_path(emission, transition)
    for t, s in enumerate(path.tolist()):
        name, _, _ = TEMPLATES[int(s)]
        conf = float(max(0.0, min(1.0, emission[t, int(s)])))
        events.append(ChordEvent(beat_index=t, chord=name, confidence=conf))
    return events


def smooth_chords(events: Iterable[ChordEvent], *, min_beats: int = 2) -> list[ChordEvent]:
    events = list(events)
    if not events:
        return []

    out: list[ChordEvent] = []
    i = 0
    while i < len(events):
        j = i + 1
        while j < len(events) and events[j].chord == events[i].chord:
            j += 1
        run_len = j - i
        if run_len < min_beats and out:
            prev = out[-1]
            for k in range(i, j):
                out.append(ChordEvent(beat_index=events[k].beat_index, chord=prev.chord, confidence=min(prev.confidence, events[k].confidence)))
        else:
            out.extend(events[i:j])
        i = j
    return out
