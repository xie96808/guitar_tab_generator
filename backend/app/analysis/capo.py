from __future__ import annotations

from dataclasses import dataclass


OPEN_CHORDS = {
    "C",
    "G",
    "D",
    "A",
    "E",
    "Am",
    "Em",
    "Dm",
    "F",
    "Bm",
}

NOTE_TO_PC = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
PC_TO_NOTE = {v: k for k, v in NOTE_TO_PC.items()}


def _parse_root(chord: str) -> tuple[str, str]:
    if not chord:
        return ("C", "")
    root = chord[0].upper()
    rest = chord[1:]
    if rest.startswith("#"):
        root += "#"
        rest = rest[1:]
    quality = ""
    if rest.startswith("m"):
        quality = "m"
    return (root, quality)


def transpose_chord(chord: str, semitones: int) -> str:
    root, quality = _parse_root(chord)
    pc = NOTE_TO_PC.get(root)
    if pc is None:
        return chord
    pc2 = (pc + semitones) % 12
    return f"{PC_TO_NOTE[pc2]}{quality}"


def capo_suggestion(chords: list[str]) -> dict:
    # We choose capo in [0..11]. With capo=k, the "shape chords" are transposed down by k.
    best = {"capo": 0, "score": 1e9}
    for capo in range(0, 12):
        score = 0.0
        for ch in chords:
            shape = transpose_chord(ch, -capo)
            if shape in OPEN_CHORDS:
                score += 0.0
            else:
                score += 1.0
            if "#" in shape:
                score += 0.2
        if score < best["score"]:
            best = {"capo": capo, "score": score}
    return {"capo": int(best["capo"]), "score": float(best["score"])}

