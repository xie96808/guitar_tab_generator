from __future__ import annotations

import io
from typing import Any

import guitarpro
from guitarpro.models import (
    BeatStatus,
    BendEffect,
    BendPoint,
    BendType,
    Chord,
    Duration,
    KeySignature,
    NoteType,
    SlideType,
    TimeSignature,
    Velocities,
)

from .score import iter_beats

KEY_SIGNATURES = {
    "C": KeySignature.CMajor,
    "G": KeySignature.GMajor,
    "D": KeySignature.DMajor,
    "A": KeySignature.AMajor,
    "E": KeySignature.EMajor,
    "B": KeySignature.BMajor,
    "F": KeySignature.FMajor,
    "Bb": KeySignature.BMajorFlat,
    "Eb": KeySignature.EMajorFlat,
    "Ab": KeySignature.AMajorFlat,
    "Am": KeySignature.AMinor,
    "Em": KeySignature.EMinor,
    "Bm": KeySignature.BMinor,
    "Dm": KeySignature.DMinor,
    "Gm": KeySignature.GMinor,
}
KEY_NAMES = {signature: name for name, signature in KEY_SIGNATURES.items()}

DYNAMIC_TO_VELOCITY = {
    "ppp": Velocities.pianoPianissimo,
    "pp": Velocities.pianissimo,
    "p": Velocities.piano,
    "mp": Velocities.mezzoPiano,
    "mf": Velocities.mezzoForte,
    "f": Velocities.forte,
    "ff": Velocities.fortissimo,
    "fff": Velocities.forteFortissimo,
}


def _duration_from_quarters(quarters: float) -> Duration:
    targets = (
        (1, 4.0),
        (2, 2.0),
        (4, 1.0),
        (8, 0.5),
        (16, 0.25),
        (32, 0.125),
    )
    for value, base in targets:
        if abs(quarters - base) < 1e-6:
            return Duration(value=value, isDotted=False)
        if abs(quarters - base * 1.5) < 1e-6:
            return Duration(value=value, isDotted=True)
    raise ValueError(f"unsupported duration {quarters}")


def _quarters_from_duration(duration: Duration) -> float:
    return float(duration.time) / float(Duration.quarterTime)


def _velocity_name(velocity: int) -> str:
    nearest = min(DYNAMIC_TO_VELOCITY, key=lambda name: abs(DYNAMIC_TO_VELOCITY[name] - velocity))
    return nearest


def _apply_time_and_key(header: guitarpro.MeasureHeader, score: dict[str, Any]) -> None:
    numerator, denominator = str(score.get("timeSignature") or "4/4").split("/")
    header.timeSignature = TimeSignature(numerator=int(numerator), denominator=Duration(value=int(denominator)))
    header.keySignature = KEY_SIGNATURES.get(str(score.get("keySignature") or "C"), KeySignature.CMajor)


def _apply_note(note: guitarpro.Note, note_score: dict[str, Any]) -> None:
    note.string = int(note_score["string"])
    note.value = int(note_score["fret"])
    if note_score.get("dead"):
        note.type = NoteType.dead
    elif note_score.get("tie"):
        note.type = NoteType.tie
    else:
        note.type = NoteType.normal
    dynamic = str(note_score.get("dynamic") or "f")
    note.velocity = DYNAMIC_TO_VELOCITY.get(dynamic, Velocities.forte)
    effect = note.effect
    effect.hammer = bool(note_score.get("hammer") or note_score.get("pull"))
    effect.vibrato = bool(note_score.get("vibrato"))
    effect.palmMute = bool(note_score.get("palmMute"))
    if note_score.get("slide"):
        effect.slides = [SlideType.shiftSlideTo]
    if note_score.get("bend"):
        semitones = int(note_score.get("bendSemitones") or 1)
        effect.bend = BendEffect(
            type=BendType.bend,
            value=semitones,
            points=[BendPoint(position=0, value=0), BendPoint(position=BendEffect.maxPosition, value=semitones)],
        )


def score_to_gp5_bytes(score: dict[str, Any]) -> bytes:
    song = guitarpro.Song()
    song.title = str(score.get("title") or "Untitled")
    song.tempo = int(score.get("tempo") or 120)
    track = song.tracks[0]
    track_score = score["tracks"][0]
    track.name = str(track_score.get("name") or "Guitar")
    bars = track_score["bars"]
    while len(song.measureHeaders) < len(bars):
        song.newMeasure()

    for index, bar in enumerate(bars):
        header = song.measureHeaders[index]
        _apply_time_and_key(header, score)
        header.isRepeatOpen = bool(bar.get("repeatStart"))
        header.repeatClose = int(bar.get("repeatEnd") or -1)
        voice = track.measures[index].voices[0]
        voice.beats = []
        for beat_score in bar["beats"]:
            beat = guitarpro.Beat(voice)
            beat.duration = _duration_from_quarters(float(beat_score["duration"]))
            if beat_score.get("rest") or not beat_score.get("notes"):
                beat.status = BeatStatus.rest
            else:
                beat.status = BeatStatus.normal
                for note_score in beat_score["notes"]:
                    note = guitarpro.Note(beat)
                    _apply_note(note, note_score)
                    beat.notes.append(note)
                if any(note.get("pull") for note in beat_score["notes"]):
                    beat.text = "p"
            chord_name = beat_score.get("chord")
            if chord_name:
                beat.effect.chord = Chord(
                    length=6,
                    name=str(chord_name),
                    firstFret=0,
                    sharp=True,
                    newFormat=True,
                    show=True,
                    add=False,
                )
            voice.beats.append(beat)

    buffer = io.BytesIO()
    guitarpro.write(song, buffer, version=(5, 1, 0))
    return buffer.getvalue()


def _note_dict(note: guitarpro.Note, quarters: float) -> dict[str, Any]:
    slides = list(note.effect.slides or [])
    bend = note.effect.bend
    payload = {
        "string": int(note.string),
        "fret": int(note.value),
        "duration": quarters,
        "dynamic": _velocity_name(int(note.velocity)),
        "tie": note.type == NoteType.tie,
        "dead": note.type == NoteType.dead,
        "hammer": bool(note.effect.hammer),
        "pull": False,
        "slide": any(slide == SlideType.shiftSlideTo for slide in slides),
        "bend": bend is not None and bool(bend.points),
        "bendSemitones": int(bend.value) if bend is not None else 0,
        "vibrato": bool(note.effect.vibrato),
        "palmMute": bool(note.effect.palmMute),
    }
    return payload


def _mark_pulls(beats: list[dict[str, Any]]) -> None:
    for beat in beats:
        if not beat.get("explicitPull"):
            continue
        for note in beat["notes"]:
            if note.get("hammer"):
                note["hammer"] = False
                note["pull"] = True


def score_from_gp5_bytes(data: bytes) -> dict[str, Any]:
    song = guitarpro.parse(io.BytesIO(data))
    header = song.measureHeaders[0]
    numerator = int(header.timeSignature.numerator)
    denominator = int(header.timeSignature.denominator.value)
    key = KEY_NAMES.get(header.keySignature, "C")
    bars: list[dict[str, Any]] = []
    for measure in song.tracks[0].measures:
        beats: list[dict[str, Any]] = []
        for beat in measure.voices[0].beats:
            if beat.status == BeatStatus.empty and not beat.notes:
                continue
            quarters = _quarters_from_duration(beat.duration)
            chord = beat.effect.chord.name if beat.effect.chord is not None else None
            explicit_pull = (beat.text or "").strip() == "p"
            if beat.status == BeatStatus.rest or not beat.notes:
                beats.append({"duration": quarters, "rest": True, "chord": chord, "notes": [], "explicitPull": explicit_pull})
                continue
            notes = sorted(
                (_note_dict(note, quarters) for note in beat.notes),
                key=lambda note: note["string"],
            )
            beats.append(
                {"duration": quarters, "rest": False, "chord": chord, "notes": notes, "explicitPull": explicit_pull}
            )
        _mark_pulls(beats)
        bars.append(
            {
                "repeatStart": bool(measure.header.isRepeatOpen),
                "repeatEnd": int(measure.header.repeatClose),
                "beats": beats,
            }
        )
    return {
        "title": song.title,
        "tempo": int(song.tempo),
        "timeSignature": f"{numerator}/{denominator}",
        "keySignature": key,
        "tracks": [{"name": song.tracks[0].name, "tuning": [64, 59, 55, 50, 45, 40], "bars": bars}],
    }


def beats_from_gp5_bytes(data: bytes) -> list[dict[str, Any]]:
    beats: list[dict[str, Any]] = []
    for bar in score_from_gp5_bytes(data)["tracks"][0]["bars"]:
        for beat in bar["beats"]:
            if beat.get("rest") or not beat["notes"]:
                continue
            beats.append(
                {
                    "duration": beat["duration"],
                    "notes": [
                        {"string": note["string"], "fret": note["fret"], "duration": note["duration"]}
                        for note in beat["notes"]
                    ],
                }
            )
    return beats


def fixture_note_rows(score: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for beat in iter_beats(score):
        rows.append(
            {
                "duration": beat["duration"],
                "notes": [
                    {"string": note["string"], "fret": note["fret"], "duration": note["duration"]}
                    for note in beat["notes"]
                ],
            }
        )
    return rows
