from __future__ import annotations

import numpy as np

NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Schmuckler key profiles (normalized later)
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88], dtype=np.float32)
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17], dtype=np.float32)


def _rot(v: np.ndarray, n: int) -> np.ndarray:
    return np.roll(v, n)


def detect_key(chroma_beat: np.ndarray) -> dict:
    if chroma_beat.size == 0 or chroma_beat.shape[1] == 0:
        return {"key": "C", "mode": "major", "confidence": 0.0, "pcs": set(range(12))}
    v = chroma_beat.mean(axis=1).astype(np.float32)
    v /= np.linalg.norm(v) + 1e-6

    maj = _MAJOR / (np.linalg.norm(_MAJOR) + 1e-6)
    minp = _MINOR / (np.linalg.norm(_MINOR) + 1e-6)

    best = ("C", "major", -1.0)
    for root in range(12):
        smaj = float(np.dot(v, _rot(maj, root)))
        if smaj > best[2]:
            best = (NOTE_NAMES_SHARP[root], "major", smaj)
        smin = float(np.dot(v, _rot(minp, root)))
        if smin > best[2]:
            best = (NOTE_NAMES_SHARP[root], "minor", smin)

    key, mode, score = best
    # Scale pcs for penalty/scoring. Use natural minor for MVP.
    root_pc = NOTE_NAMES_SHARP.index(key)
    if mode == "major":
        scale = {0, 2, 4, 5, 7, 9, 11}
    else:
        scale = {0, 2, 3, 5, 7, 8, 10}
    pcs = {(root_pc + i) % 12 for i in scale}
    conf = float(max(0.0, min(1.0, (score + 0.2))))  # loose mapping into [0,1]
    return {"key": key, "mode": mode, "confidence": conf, "pcs": pcs}

