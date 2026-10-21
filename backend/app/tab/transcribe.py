from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy.io import wavfile

from .drafts import pack_beats
from .fingering import finger_beats

SCALE_PITCHES = [60, 62, 64, 65, 67, 69, 71, 72]


def synthesize_notes(pitches: list[int], bpm: int = 120, sr: int = 22050) -> np.ndarray:
    quarter = 60.0 / bpm
    chunks: list[np.ndarray] = []
    for midi in pitches:
        freq = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        total = int(sr * quarter)
        gap = int(sr * 0.04)
        tone_n = total - gap
        t = np.arange(tone_n) / sr
        window = np.hanning(tone_n)
        tone = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 2 * t)
        chunks.append(0.6 * tone * window)
        chunks.append(np.zeros(gap))
    return np.concatenate(chunks).astype(np.float32)


def write_wav(path: Path, audio: np.ndarray, sr: int = 22050) -> None:
    pcm = np.clip(audio, -1, 1)
    wavfile.write(str(path), sr, (pcm * 32767).astype(np.int16))


def encode_audio(wav_path: Path, dest: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path), str(dest)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def load_mono(path: Path) -> tuple[int, np.ndarray]:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        sr, data = wavfile.read(str(path))
    else:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            temp = Path(handle.name)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(path), "-ac", "1", "-ar", "22050", str(temp)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            sr, data = wavfile.read(str(temp))
        finally:
            temp.unlink(missing_ok=True)
    audio = np.asarray(data, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    peak = float(np.max(np.abs(audio))) or 1.0
    if peak > 2:
        audio = audio / 32768.0
    return int(sr), audio


def _pitch_midi(frame: np.ndarray, sr: int) -> Optional[int]:
    frame = frame - float(np.mean(frame))
    if float(np.max(np.abs(frame))) < 0.05:
        return None
    corr = np.correlate(frame, frame, mode="full")[len(frame) - 1 :]
    low = max(1, int(sr / 1000))
    high = min(len(corr) - 1, int(sr / 60))
    if high <= low:
        return None
    lag = low + int(np.argmax(corr[low:high]))
    if corr[lag] <= 0:
        return None
    freq = sr / lag
    if freq <= 0:
        return None
    midi = int(round(69 + 12 * np.log2(freq / 440.0)))
    if midi < 36 or midi > 90:
        return None
    return midi


def transcribe_audio(path: Path, title: str | None = None) -> dict[str, Any]:
    sr, audio = load_mono(path)
    hop = max(1, int(sr * 0.01))
    energy = np.array(
        [float(np.sqrt(np.mean(audio[i : i + hop] ** 2))) for i in range(0, len(audio) - hop, hop)]
    )
    if len(energy) == 0:
        raise ValueError("audio is empty")
    threshold = max(0.03, float(np.max(energy)) * 0.35)
    active = energy > threshold
    regions: list[tuple[int, int]] = []
    start = None
    for index, flag in enumerate(active):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            if index - start > 8:
                regions.append((start, index))
            start = None
    if start is not None and len(active) - start > 8:
        regions.append((start, len(active)))
    notes: list[tuple[int, float]] = []
    for begin, end in regions:
        sample_start = begin * hop
        sample_end = min(len(audio), end * hop)
        midi = _pitch_midi(audio[sample_start:sample_end], sr)
        if midi is None:
            continue
        seconds = (sample_end - sample_start) / sr
        notes.append((midi, seconds))
    if not notes:
        raise ValueError("no notes detected")
    quarter = float(np.median([seconds for _, seconds in notes]))
    quarter = max(quarter, 0.2)
    pitches = []
    durations = []
    for midi, seconds in notes:
        grid = max(0.5, round((seconds / quarter) * 2) / 2)
        pitches.append([midi])
        durations.append(grid)
    fingered = finger_beats(pitches)
    beats = []
    for notes_on_beat, duration in zip(fingered, durations):
        beats.append(
            {
                "duration": duration,
                "rest": False,
                "notes": [
                    {"string": note.string, "fret": note.fret, "duration": duration, "dynamic": "f"}
                    for note in notes_on_beat
                ],
            }
        )
    return {
        "title": title or path.stem,
        "tempo": int(round(60.0 / quarter)),
        "timeSignature": "4/4",
        "keySignature": "C",
        "tracks": [
            {
                "name": "Guitar",
                "tuning": [64, 59, 55, 50, 45, 40],
                "bars": pack_beats(beats, "4/4"),
            }
        ],
    }


def sounding_midis(score: dict[str, Any]) -> list[int]:
    from .fingering import OPEN_MIDI

    midis = []
    for bar in score["tracks"][0]["bars"]:
        for beat in bar["beats"]:
            for note in beat.get("notes") or []:
                midis.append(OPEN_MIDI[int(note["string"])] + int(note["fret"]))
    return midis
