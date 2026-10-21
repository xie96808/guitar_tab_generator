from __future__ import annotations

from copy import deepcopy
from typing import Any

from .fingering import OPEN_MIDI, finger_beats


def _beat(score: dict[str, Any], bar: int, beat: int) -> dict[str, Any]:
    return score["tracks"][0]["bars"][bar]["beats"][beat]


def _note(score: dict[str, Any], bar: int, beat: int, note: int) -> dict[str, Any]:
    return _beat(score, bar, beat)["notes"][note]


def _retarget(score: dict[str, Any], semitones: int) -> None:
    pitches: list[list[int]] = []
    durations: list[float] = []
    flags: list[list[dict[str, Any]]] = []
    for bar in score["tracks"][0]["bars"]:
        for beat in bar["beats"]:
            if beat.get("rest") or not beat.get("notes"):
                continue
            sounding = []
            kept = []
            for note in beat["notes"]:
                midi = OPEN_MIDI[int(note["string"])] + int(note["fret"]) + semitones
                if midi < 40 or midi > 64 + 22:
                    continue
                sounding.append(midi)
                kept.append(note)
            if not sounding:
                beat["rest"] = True
                beat["notes"] = []
                continue
            pitches.append(sounding)
            durations.append(float(beat["duration"]))
            flags.append(kept)
    fingered = finger_beats(pitches)
    cursor = 0
    for bar in score["tracks"][0]["bars"]:
        for beat in bar["beats"]:
            if beat.get("rest") or not beat.get("notes"):
                continue
            notes = fingered[cursor]
            previous = flags[cursor]
            beat["notes"] = [
                {
                    **previous[min(index, len(previous) - 1)],
                    "string": note.string,
                    "fret": note.fret,
                    "duration": durations[cursor],
                }
                for index, note in enumerate(notes)
            ]
            beat["rest"] = False
            cursor += 1


def apply_edit(score: dict[str, Any], edit: dict[str, Any]) -> dict[str, Any]:
    score = deepcopy(score)
    kind = edit["op"]
    if kind == "set_fret":
        _note(score, edit["bar"], edit["beat"], edit["note"])["fret"] = int(edit["fret"])
    elif kind == "set_string":
        _note(score, edit["bar"], edit["beat"], edit["note"])["string"] = int(edit["string"])
    elif kind == "set_duration":
        quarters = float(edit["duration"])
        if edit.get("dotted"):
            quarters *= 1.5
        beat = _beat(score, edit["bar"], edit["beat"])
        beat["duration"] = quarters
        for note in beat["notes"]:
            note["duration"] = quarters
    elif kind == "set_tempo":
        score["tempo"] = int(edit["tempo"])
    elif kind == "set_time_signature":
        score["timeSignature"] = f'{int(edit["numerator"])}/{int(edit["denominator"])}'
    elif kind == "set_key":
        score["keySignature"] = str(edit["key"])
    elif kind == "set_dynamic":
        _note(score, edit["bar"], edit["beat"], edit["note"])["dynamic"] = str(edit["dynamic"])
    elif kind == "set_rest":
        beat = _beat(score, edit["bar"], edit["beat"])
        beat["rest"] = True
        beat["notes"] = []
    elif kind == "set_tie":
        _note(score, edit["bar"], edit["beat"], edit["note"])["tie"] = bool(edit.get("value", True))
    elif kind == "set_dead":
        _note(score, edit["bar"], edit["beat"], edit["note"])["dead"] = bool(edit.get("value", True))
    elif kind == "set_hammer":
        _note(score, edit["bar"], edit["beat"], edit["note"])["hammer"] = True
        _note(score, edit["bar"], edit["beat"], edit["note"])["pull"] = False
    elif kind == "set_pull":
        _note(score, edit["bar"], edit["beat"], edit["note"])["pull"] = True
        _note(score, edit["bar"], edit["beat"], edit["note"])["hammer"] = False
    elif kind == "set_slide":
        _note(score, edit["bar"], edit["beat"], edit["note"])["slide"] = True
    elif kind == "set_bend":
        note = _note(score, edit["bar"], edit["beat"], edit["note"])
        note["bend"] = True
        note["bendSemitones"] = int(edit.get("semitones") or 1)
    elif kind == "set_vibrato":
        _note(score, edit["bar"], edit["beat"], edit["note"])["vibrato"] = True
    elif kind == "set_palm_mute":
        _note(score, edit["bar"], edit["beat"], edit["note"])["palmMute"] = True
    elif kind == "set_chord":
        _beat(score, edit["bar"], edit["beat"])["chord"] = str(edit["name"])
    elif kind == "set_repeat":
        bars = score["tracks"][0]["bars"]
        bars[int(edit["start"])]["repeatStart"] = True
        bars[int(edit["end"])]["repeatEnd"] = int(edit.get("count") or 1)
    elif kind == "add_note":
        beat = _beat(score, edit["bar"], edit["beat"])
        beat["rest"] = False
        beat["notes"].append(
            {
                "string": int(edit["string"]),
                "fret": int(edit["fret"]),
                "duration": float(beat["duration"]),
                "dynamic": "f",
            }
        )
    elif kind == "delete_note":
        beat = _beat(score, edit["bar"], edit["beat"])
        del beat["notes"][int(edit["note"])]
        if not beat["notes"]:
            beat["rest"] = True
    elif kind == "delete_bar":
        bars = score["tracks"][0]["bars"]
        del bars[int(edit["bar"])]
        if not bars:
            bars.append({"repeatStart": False, "repeatEnd": -1, "beats": [{"duration": 1, "rest": True, "notes": []}]})
    elif kind == "copy_bar":
        bars = score["tracks"][0]["bars"]
        bars.insert(int(edit["bar"]) + 1, deepcopy(bars[int(edit["bar"])]))
    elif kind == "quantize":
        grid = float(edit.get("grid") or 0.5)
        for bar in score["tracks"][0]["bars"]:
            for beat in bar["beats"]:
                quarters = max(grid, round(float(beat["duration"]) / grid) * grid)
                beat["duration"] = quarters
                for note in beat["notes"]:
                    note["duration"] = quarters
    elif kind == "transpose":
        _retarget(score, int(edit["semitones"]))
    else:
        raise ValueError(f"unknown edit {kind}")
    return score
